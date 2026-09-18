"""Acceptance matrix for V4.1 bounded neighborhood reads (HANDOFF §9)."""

from __future__ import annotations

import ast
import hashlib
import json
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
from dungeonmind.application.vnext.errors import (
    CandidateAdmissionIntegrityError,
    NeighborhoodReadIntegrityError,
)
from dungeonmind.application.vnext.frozen_json import FrozenDict
from dungeonmind.application.vnext.model import ParsedKnowledgeRevision
from dungeonmind.application.vnext.neighborhood import (
    MAX_NEIGHBORHOOD_SEED_COUNT,
    NeighborhoodReadService,
)
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.records import ParsedEntityRefValue
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
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
from dungeonmind.domain.canonical import canonical_sha256
from tests.unit.test_vnext_knowledge_read_context import (
    CANONICAL_V0_AGGREGATE,
    ORG_CONTRACT_DIGEST,
    ORG_PROFILE_DIGEST,
    REPO_ROOT,
    VNEXT_SRC,
    _buddy_context,
    _buddy_request,
    _build_from_fixture,
    _org_domain_contract,
    _org_semantic_profile,
    _refresh_org_context,
)

STEWARD_PATH = REPO_ROOT / "Docs" / "Handoffs" / "HANDOFF-STEWARDSHIP-vnext-roadmap.md"
V41_HANDOFF_PATH = REPO_ROOT / "Docs" / "Handoffs" / "HANDOFF-v4-1-bounded-neighborhood.md"
NEIGHBORHOOD_BENCH_PATH = REPO_ROOT / "Docs" / "Benchmarks" / "vnext_neighborhood_10k_v1.json"

_SVC = NeighborhoodReadService()
IMPLEMENTATION_BASE = "82a5c3e6889ad4e5648fef8f358423b5a576cb9b"
V3_MERGE = "c12bf89ea54af1112a0e98163aa224eb89b11c22"
V3_HEAD = "6c8adb474d84df6dc6e1d55cec6bedb2380e100b"
V3_REVIEW = "5224138590"


def _lab_contract() -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.neighborhood",
        domain_revision="1",
        scope_axes=["test:scope"],
        visibility_labels=["test:audience", "test:hidden"],
        claim_modes=["test:fact"],
        admission_policy_id="test.always",
    )


def _lab_profile() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.neighborhood.profile",
        profile_revision="1",
        term_namespaces=["test"],
        predicates=[
            SemanticProfilePredicate(term="test:relates", allowed_value_kinds=["entity_ref"]),
            SemanticProfilePredicate(term="test:title", allowed_value_kinds=["literal"]),
        ],
    )


def _meta(
    *,
    evidence_id: str = "evidence:lab",
    scope_value: str = "one",
    visibility: PublicVisibility | LabelsAnyVisibility | LabelsAllVisibility | None = None,
) -> AssertionMetadata:
    return AssertionMetadata(
        scope=[ScopeBinding(axis="test:scope", value=scope_value)],
        visibility=visibility or PublicVisibility(),
        epistemic_basis=EpistemicBasis.ASSERTED,
        claim_mode="test:fact",
        standing=KnowledgeStanding.ESTABLISHED,
        evidence_ref_ids=[evidence_id],
        temporal_scope=TimelessTemporalScope(),
    )


def _edge(
    assertion_id: str,
    subject: str,
    target: str,
    *,
    evidence_id: str = "evidence:lab",
    scope_value: str = "one",
    visibility: PublicVisibility | LabelsAnyVisibility | LabelsAllVisibility | None = None,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="test:relates",
        value=EntityRefValue(entity_id=target),
        metadata=_meta(evidence_id=evidence_id, scope_value=scope_value, visibility=visibility),
    )


def _literal(assertion_id: str, subject: str, *, evidence_id: str = "evidence:lab") -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="test:title",
        value=LiteralValue(value={"n": assertion_id}),
        metadata=_meta(evidence_id=evidence_id),
    )


def _evidence(evidence_id: str, artifact_id: str, revision_id: str) -> EvidenceRefV3:
    return EvidenceRefV3(
        evidence_ref_id=evidence_id,
        source_artifact_id=artifact_id,
        source_revision_id=revision_id,
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=False,
    )


def _artifact(artifact_id: str, revision_id: str, *, status: str = "active") -> SourceArtifactV3:
    return SourceArtifactV3(
        source_artifact_id=artifact_id,
        source_classification="test:doc",
        current_revision_id=revision_id,
        authority="primary",
        visibility=PublicVisibility(),
        status=status,
    )


def _revision(revision_id: str, artifact_id: str, digest: str = "c" * 64) -> SourceRevisionV2:
    return SourceRevisionV2(
        source_revision_id=revision_id,
        source_artifact_id=artifact_id,
        content_sha256=digest,
        body_storage="inline",
        created_at=datetime(2026, 9, 16, tzinfo=UTC),
    )


def _lab_context(
    *,
    entities: list[Entity],
    assertions: list[Assertion],
    evidence: list[EvidenceRefV3] | None = None,
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
        artifacts = {"src:lab": _artifact("src:lab", "srcrev:lab")}
    if revisions is None:
        revisions = {"srcrev:lab": _revision("srcrev:lab", "src:lab")}
    if evidence is None:
        evidence = [_evidence("evidence:lab", "src:lab", "srcrev:lab")]
    revision = KnowledgeRevision(
        space_id=space_id,
        revision_id=revision_id,
        created_at=datetime(2026, 9, 16, tzinfo=UTC),
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
    context = KnowledgeReadContext(
        parsed=parsed,
        request=resolved_request,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        domain_policy=policy or AlwaysAdmitPolicy(policy_id=domain_contract.admission_policy_id),
        source_reader=reader,
    )
    return context, reader


def _rebind(
    context: KnowledgeReadContext, reader: InMemoryKnowledgeSourceReader
) -> KnowledgeReadContext:
    return KnowledgeReadContext(
        parsed=context.parsed,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=reader,
    )


def _chain_lab() -> KnowledgeReadContext:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")],
        assertions=[_edge("asrt:ab", "A", "B"), _edge("asrt:bc", "B", "C")],
    )
    return context


def _privacy_lab() -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    return _lab_context(
        entities=[
            Entity(entity_id="seed"),
            Entity(entity_id="public"),
            Entity(entity_id="secret"),
        ],
        assertions=[
            _edge("asrt:public", "seed", "public", evidence_id="evidence:visible"),
            _edge(
                "asrt:secret",
                "seed",
                "secret",
                evidence_id="evidence:hidden",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            ),
        ],
        evidence=[
            _evidence("evidence:visible", "src:visible", "srcrev:visible"),
            _evidence("evidence:hidden", "src:hidden", "srcrev:hidden"),
        ],
        artifacts={
            "src:visible": _artifact("src:visible", "srcrev:visible"),
            "src:hidden": _artifact("src:hidden", "srcrev:hidden"),
        },
        revisions={
            "srcrev:visible": _revision("srcrev:visible", "src:visible", "a" * 64),
            "srcrev:hidden": _revision("srcrev:hidden", "src:hidden", "b" * 64),
        },
    )


def _ids(result: Any) -> set[str]:
    return {item.entity_id for item in result.entities}


def _asrt_ids(result: Any) -> set[str]:
    return {item.assertion_id for item in result.traversal_assertions}


def _depth_map(result: Any) -> dict[str, int]:
    return dict(result.entity_depths)


# --- A. Dispatch / exact seeds ---


def test_01_implementation_base_recorded() -> None:
    steward = STEWARD_PATH.read_text(encoding="utf-8")
    handoff = V41_HANDOFF_PATH.read_text(encoding="utf-8")
    assert IMPLEMENTATION_BASE in steward
    assert IMPLEMENTATION_BASE in handoff
    assert "V4.1 COMPLETE" in steward
    assert "V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED" in steward
    assert "V4.2 COMPLETE" in steward
    assert "V4.3 COMPLETE" in steward
    assert "V5.1 ACTIVE" in steward
    assert "IMPLEMENTATION NOT YET ACCEPTED" in steward
    assert "implementation now proceeding from current main" in handoff


def test_02_v3_predecessor_recorded() -> None:
    steward = STEWARD_PATH.read_text(encoding="utf-8")
    assert V3_MERGE in steward
    assert V3_HEAD in steward
    assert V3_REVIEW in steward
    assert "V3_LAZY_EXACT_COMPLETE_ENTITY_READS_ACCEPTED" in steward


def test_03_frozen_v0_aggregate_remains_exact() -> None:
    bundle = (REPO_ROOT / "Docs" / "Contracts" / "vnext" / "dm_vnext_contract_v1.json").read_text()
    assert CANONICAL_V0_AGGREGATE in bundle


def test_04_exact_seed_returns_depth_zero() -> None:
    context = _chain_lab()
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    assert result.found_seed_entity_ids == ("A",)
    assert result.missing_seed_entity_ids == ()
    assert _depth_map(result)["A"] == 0
    assert result.completeness.status == "complete"


def test_05_missing_seed_is_explicit() -> None:
    context = _chain_lab()
    result = _SVC.get_neighborhood(context, ["missing"], depth=1)
    assert result.found_seed_entity_ids == ()
    assert result.missing_seed_entity_ids == ("missing",)
    assert result.entities == ()
    assert result.traversal_assertions == ()


def test_06_isolated_seed_still_returns_depth_zero() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="lonely")],
        assertions=[],
        evidence=[],
    )
    result = _SVC.get_neighborhood(context, ["lonely"], depth=1)
    assert result.found_seed_entity_ids == ("lonely",)
    assert _depth_map(result) == {"lonely": 0}
    assert result.traversal_assertions == ()
    assert result.work.assertions_evaluated == 0
    assert result.work.provenance_snapshot_calls == 0


def test_07_duplicate_seeds_are_deduped() -> None:
    context = _chain_lab()
    result = _SVC.get_neighborhood(context, ["A", "A"], depth=1)
    assert result.requested_seed_entity_ids == ("A",)
    assert result.work.seed_entity_lookups == 1


def test_08_seed_order_does_not_change_semantic_result() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")],
        assertions=[_edge("asrt:ac", "A", "C"), _edge("asrt:bc", "B", "C")],
    )
    first = _SVC.get_neighborhood(context, ["A", "B"], depth=1)
    second = _SVC.get_neighborhood(context, ["B", "A"], depth=1)
    third = _SVC.get_neighborhood(context, ["B", "A", "B"], depth=1)
    assert first.requested_seed_entity_ids == ("A", "B")
    assert first == second == third


def test_09_too_many_seeds_fails_explicitly() -> None:
    context = _chain_lab()
    seeds = [f"s{i}" for i in range(MAX_NEIGHBORHOOD_SEED_COUNT + 1)]
    with pytest.raises(NeighborhoodReadIntegrityError, match="at most"):
        _SVC.get_neighborhood(context, seeds, depth=1)


def test_10_empty_seeds_fail() -> None:
    context = _chain_lab()
    with pytest.raises(NeighborhoodReadIntegrityError, match="at least one"):
        _SVC.get_neighborhood(context, [], depth=1)


# --- B. Depth ---


def test_11_depth_1_returns_admitted_touching_edges_and_endpoints() -> None:
    context = _chain_lab()
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    assert _asrt_ids(result) == {"asrt:ab"}
    assert _ids(result) == {"A", "B"}
    assert _depth_map(result) == {"A": 0, "B": 1}
    assert "C" not in _ids(result)


def test_12_depth_1_does_not_expand_endpoints() -> None:
    context = _chain_lab()
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    assert result.work.layers[0].frontier_entities_expanded == 1
    assert len(result.work.layers) == 1


def test_13_depth_2_expands_only_depth_1_frontier() -> None:
    context = _chain_lab()
    result = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert _ids(result) == {"A", "B", "C"}
    assert _depth_map(result)["C"] == 2
    assert _asrt_ids(result) == {"asrt:ab", "asrt:bc"}
    assert result.work.layers[0].frontier_entities_expanded == 1
    assert result.work.layers[1].frontier_entities_expanded == 1


def test_14_depth_2_entities_are_not_expanded() -> None:
    entities = [Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")]
    assertions = [_edge("asrt:ab", "A", "B"), _edge("asrt:bc", "B", "C")]
    for index in range(40):
        entities.append(Entity(entity_id=f"D{index:02d}"))
        assertions.append(_edge(f"asrt:cd-{index:02d}", "C", f"D{index:02d}"))
    context, _ = _lab_context(entities=entities, assertions=assertions)
    result = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert "C" in _ids(result)
    assert all(not item.startswith("D") for item in _ids(result))
    assert result.work.layers[-1].touching_assertion_candidates == 2
    assert all("asrt:cd-" not in assertion_id for assertion_id in _asrt_ids(result))


def test_15_minimum_depth_wins_on_converging_paths() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")],
        assertions=[
            _edge("asrt:ab", "A", "B"),
            _edge("asrt:bc", "B", "C"),
            _edge("asrt:ac", "A", "C"),
        ],
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert _depth_map(result)["C"] == 1


def test_16_direct_seed_to_c_beats_longer_path() -> None:
    test_15_minimum_depth_wins_on_converging_paths()


def test_17_invalid_depth_fails() -> None:
    context = _chain_lab()
    for depth in (0, 3, -1, 1.5, True, False, "1"):
        with pytest.raises(NeighborhoodReadIntegrityError, match="exactly 1 or 2"):
            _SVC.get_neighborhood(context, ["A"], depth=depth)  # type: ignore[arg-type]


# --- C. Admission / privacy ---


def test_18_hidden_edge_does_not_leak_unique_endpoint() -> None:
    context, _ = _privacy_lab()
    result = _SVC.get_neighborhood(context, ["seed"], depth=1)
    assert "secret" not in _ids(result)
    assert "public" in _ids(result)
    assert "asrt:secret" not in _asrt_ids(result)


def test_19_scope_exclusion_does_not_leak_endpoint() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="seed"), Entity(entity_id="other")],
        assertions=[_edge("asrt:other", "seed", "other", scope_value="two")],
    )
    result = _SVC.get_neighborhood(context, ["seed"], depth=1)
    assert "other" not in _ids(result)
    assert _asrt_ids(result) == set()


def test_20_wildcard_scope_can_admit_otherwise_valid_edge() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="seed"), Entity(entity_id="other")],
        assertions=[_edge("asrt:other", "seed", "other", scope_value="two")],
        request=ProjectionRequest(
            space_id="space:lab",
            revision_id="rev:lab",
            scope_selector=ScopeSelector(
                include_unscoped=True,
                bindings=[],
                wildcard_axes=["test:scope"],
            ),
            audience_labels=["test:audience"],
            standing_selector=[KnowledgeStanding.ESTABLISHED],
        ),
    )
    result = _SVC.get_neighborhood(context, ["seed"], depth=1)
    assert "other" in _ids(result)
    assert "asrt:other" in _asrt_ids(result)


def test_21_inactive_source_removes_edge() -> None:
    context, reader = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[_edge("asrt:ab", "A", "B")],
    )
    artifact = reader._artifacts["src:lab"]
    reader._artifacts["src:lab"] = artifact.model_copy(update={"status": "inactive"})
    result = _SVC.get_neighborhood(_rebind(context, reader), ["A"], depth=1)
    assert "B" not in _ids(result)
    assert _asrt_ids(result) == set()


def test_22_missing_source_excludes_edge_without_leak() -> None:
    context, reader = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[_edge("asrt:ab", "A", "B")],
    )
    reader._artifacts.clear()
    result = _SVC.get_neighborhood(_rebind(context, reader), ["A"], depth=1)
    assert "B" not in _ids(result)


def test_23_unknown_candidate_fails_closed() -> None:
    context = _chain_lab()
    parsed = context.parsed
    corrupted_outgoing = dict(parsed.entity_ref_outgoing_assertions)
    corrupted_outgoing["A"] = (*corrupted_outgoing.get("A", ()), "asrt:missing")
    broken_parsed = replace(
        parsed,
        entity_ref_outgoing_assertions=FrozenDict(corrupted_outgoing),
    )
    broken = KnowledgeReadContext(
        parsed=broken_parsed,
        request=context.request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=context.source_reader,
    )
    with pytest.raises(CandidateAdmissionIntegrityError):
        _SVC.get_neighborhood(broken, ["A"], depth=1)


def test_24_domain_policy_excluded_edge_does_not_traverse() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")],
        assertions=[_edge("asrt:ab", "A", "B"), _edge("asrt:ac", "A", "C")],
        policy=ExcludeByAssertionIdPolicy(
            policy_id="test.always",
            excluded_assertion_ids=frozenset({"asrt:ac"}),
        ),
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    assert "C" not in _ids(result)
    assert "B" in _ids(result)


def test_25_buddy_player_audience_excludes_gm_only_edge() -> None:
    ctx, _ = _buddy_context(
        _buddy_request(campaign="C2", audience=["dungeonbuddy.visibility:player"])
    )
    result = _SVC.get_neighborhood(ctx, ["npc:hero"], depth=1)
    assert "asrt:c2-gm-only" not in _asrt_ids(result)
    assert "asrt:c3-gm-secret" not in _asrt_ids(result)
    assert "asrt:c2-player-fact" in _asrt_ids(result)


def test_26_focus_does_not_broaden_authority() -> None:
    baseline_ctx, _ = _buddy_context(_buddy_request(campaign="C2"))
    focused_ctx, _ = _buddy_context(
        _buddy_request(
            campaign="C2",
            focus=[FocusRef(kind="dungeonbuddy:session", id="sess-42")],
            domain_context=["dungeonbuddy:session"],
        )
    )
    baseline = _SVC.get_neighborhood(baseline_ctx, ["npc:hero"], depth=1)
    focused = _SVC.get_neighborhood(focused_ctx, ["npc:hero"], depth=1)
    assert _asrt_ids(baseline) == _asrt_ids(focused)


# --- D. Direction and graph shape ---


def test_27_outgoing_direction_preserved() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[_edge("asrt:ab", "A", "B")],
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    assertion = result.traversal_assertions[0]
    assert assertion.subject_entity_id == "A"
    assert isinstance(assertion.value, ParsedEntityRefValue)
    assert assertion.value.entity_id == "B"


def test_28_incoming_direction_preserved() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[_edge("asrt:ba", "B", "A")],
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    assertion = result.traversal_assertions[0]
    assert assertion.subject_entity_id == "B"
    assert isinstance(assertion.value, ParsedEntityRefValue)
    assert assertion.value.entity_id == "A"
    assert _depth_map(result)["B"] == 1


def test_29_self_loop_returned_once_without_new_entity() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_edge("asrt:aa", "A", "A")],
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert _asrt_ids(result) == {"asrt:aa"}
    assert _ids(result) == {"A"}
    assert result.work.endpoint_entity_lookups == 0


def test_30_cycle_a_b_a_terminates() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[_edge("asrt:ab", "A", "B"), _edge("asrt:ba", "B", "A")],
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert _ids(result) == {"A", "B"}
    assert _asrt_ids(result) == {"asrt:ab", "asrt:ba"}


def test_31_triangle_terminates() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")],
        assertions=[
            _edge("asrt:ab", "A", "B"),
            _edge("asrt:bc", "B", "C"),
            _edge("asrt:ca", "C", "A"),
        ],
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert _ids(result) == {"A", "B", "C"}
    assert len(result.traversal_assertions) == 3


def test_32_converging_paths_dedupe() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")],
        assertions=[_edge("asrt:ac", "A", "C"), _edge("asrt:bc", "B", "C")],
    )
    result = _SVC.get_neighborhood(context, ["A", "B"], depth=1)
    assert list(_ids(result)).count("C") == 1
    assert len([item for item in result.entities if item.entity_id == "C"]) == 1


def test_33_parallel_admitted_edges_preserved() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[_edge("asrt:ab-1", "A", "B"), _edge("asrt:ab-2", "A", "B")],
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    assert _asrt_ids(result) == {"asrt:ab-1", "asrt:ab-2"}
    assert _ids(result) == {"A", "B"}


def test_34_hidden_parallel_edge_does_not_duplicate_or_leak() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="secret")],
        assertions=[
            _edge("asrt:ab", "A", "B", evidence_id="evidence:visible"),
            _edge(
                "asrt:secret",
                "A",
                "secret",
                evidence_id="evidence:hidden",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            ),
        ],
        evidence=[
            _evidence("evidence:visible", "src:visible", "srcrev:visible"),
            _evidence("evidence:hidden", "src:hidden", "srcrev:hidden"),
        ],
        artifacts={
            "src:visible": _artifact("src:visible", "srcrev:visible"),
            "src:hidden": _artifact("src:hidden", "srcrev:hidden"),
        },
        revisions={
            "srcrev:visible": _revision("srcrev:visible", "src:visible"),
            "srcrev:hidden": _revision("srcrev:hidden", "src:hidden"),
        },
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    assert _asrt_ids(result) == {"asrt:ab"}
    assert "secret" not in _ids(result)


# --- E. Structural locality ---


def test_35_unrelated_growth_does_not_expand_candidates() -> None:
    def build(decoys: int) -> KnowledgeReadContext:
        entities = [Entity(entity_id="A"), Entity(entity_id="B")]
        assertions = [_edge("asrt:ab", "A", "B")]
        for index in range(decoys):
            entities.append(Entity(entity_id=f"decoy-{index:04d}"))
            assertions.append(_literal(f"asrt:decoy-{index:04d}", f"decoy-{index:04d}"))
        context, _ = _lab_context(entities=entities, assertions=assertions)
        return context

    small = _SVC.get_neighborhood(build(20), ["A"], depth=1)
    large = _SVC.get_neighborhood(build(400), ["A"], depth=1)
    assert small.work.deduped_candidate_assertions == large.work.deduped_candidate_assertions == 1
    assert small.work.assertions_evaluated == large.work.assertions_evaluated == 1
    assert small.work.artifact_ids_requested == large.work.artifact_ids_requested


def test_36_noisy_neighbor_literals_are_not_scanned() -> None:
    entities = [Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")]
    assertions = [_edge("asrt:ab", "A", "B"), _edge("asrt:bc", "B", "C")]
    for index in range(800):
        assertions.append(_literal(f"asrt:noise-{index:04d}", "B"))
    context, _ = _lab_context(entities=entities, assertions=assertions)
    lookup_count = {"n": 0}
    original = ParsedKnowledgeRevision.get_assertion

    def counting(self: ParsedKnowledgeRevision, assertion_id: str) -> Any:
        lookup_count["n"] += 1
        return original(self, assertion_id)

    with patch.object(ParsedKnowledgeRevision, "get_assertion", counting):
        result = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert _asrt_ids(result) == {"asrt:ab", "asrt:bc"}
    assert result.work.assertions_evaluated == 2
    assert lookup_count["n"] < 40
    assert lookup_count["n"] < 800


def test_37_high_degree_seed_work_scales_honestly() -> None:
    def build(degree: int) -> KnowledgeReadContext:
        entities = [Entity(entity_id="hub")]
        assertions = []
        for index in range(degree):
            entities.append(Entity(entity_id=f"n{index:02d}"))
            assertions.append(_edge(f"asrt:hub-{index:02d}", "hub", f"n{index:02d}"))
        context, _ = _lab_context(entities=entities, assertions=assertions)
        return context

    small = _SVC.get_neighborhood(build(4), ["hub"], depth=1)
    large = _SVC.get_neighborhood(build(30), ["hub"], depth=1)
    assert small.work.assertions_evaluated == 4
    assert large.work.assertions_evaluated == 30
    assert large.work.returned_traversal_assertions == 30


def test_38_no_world_projection_import() -> None:
    source = (VNEXT_SRC / "neighborhood.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "world_graph_projection" not in source
    assert "world_graph_retrieval" not in source
    assert "dungeonmind_dnd" not in imported


def test_39_generic_code_has_no_ttrpg_vocabulary() -> None:
    source = (VNEXT_SRC / "neighborhood.py").read_text(encoding="utf-8")
    for token in ("GM", "PLAYER", "campaign_id", "NPC", "fictional-time", "dnd"):
        assert token not in source


# --- F. Coherence / freshness ---


def test_40_depth_2_stays_on_one_pinned_context() -> None:
    context = _chain_lab()
    first = _SVC.get_neighborhood(context, ["A"], depth=2)
    second = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert first.result_digest == second.result_digest
    assert context.parsed.revision_id == first.identity.revision_id


def test_41_live_source_change_does_not_tear_same_context() -> None:
    context, reader = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[_edge("asrt:ab", "A", "B")],
    )
    first = _SVC.get_neighborhood(context, ["A"], depth=2)
    artifact = reader._artifacts["src:lab"]
    reader._artifacts["src:lab"] = artifact.model_copy(update={"status": "inactive"})
    second = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert first.result_digest == second.result_digest
    assert "B" in _ids(second)


def test_42_new_context_observes_changed_authority() -> None:
    context, reader = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[_edge("asrt:ab", "A", "B")],
    )
    first = _SVC.get_neighborhood(context, ["A"], depth=1)
    artifact = reader._artifacts["src:lab"]
    reader._artifacts["src:lab"] = artifact.model_copy(update={"status": "inactive"})
    refreshed = _rebind(context, reader)
    second = _SVC.get_neighborhood(refreshed, ["A"], depth=1)
    assert first.result_digest != second.result_digest
    assert "B" not in _ids(second)


# --- G. Genericity ---


def test_43_organizational_memory_fixture_traverses() -> None:
    context, _ = _build_from_fixture(
        "organizational_memory_v1.json",
        domain_contract=_org_domain_contract(),
        semantic_profile=_org_semantic_profile(),
        contract_digest=ORG_CONTRACT_DIGEST,
        profile_digest=ORG_PROFILE_DIGEST,
    )
    result = _SVC.get_neighborhood(context, ["priya"], depth=1)
    assert result.found_seed_entity_ids == ("priya",)
    assert "retrieval-evaluation" in _ids(result) or "research-team" in _ids(result)
    assert result.work.assertions_evaluated == result.work.deduped_candidate_assertions


def test_44_buddy_opaque_labels_only() -> None:
    ctx, _ = _buddy_context(_buddy_request(campaign="C2"))
    result = _SVC.get_neighborhood(ctx, ["npc:hero"], depth=1)
    assert "loc:tavern" in _ids(result)
    source = (VNEXT_SRC / "neighborhood.py").read_text(encoding="utf-8")
    assert "dungeonbuddy" not in source


# --- H. Immutability / digest ---


def test_45_result_is_immutable() -> None:
    context = _chain_lab()
    result = _SVC.get_neighborhood(context, ["A"], depth=1)
    with pytest.raises((AttributeError, TypeError)):
        result.requested_depth = 2  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError, ValueError)):
        result.entity_depths[0] = ("A", 9)  # type: ignore[index]


def test_46_repeated_read_is_deterministic() -> None:
    context = _chain_lab()
    first = _SVC.get_neighborhood(context, ["A"], depth=2)
    second = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert first.result_digest == second.result_digest
    assert first.entity_depths == second.entity_depths
    assert [item.assertion_id for item in first.traversal_assertions] == [
        item.assertion_id for item in second.traversal_assertions
    ]


def test_47_work_counters_do_not_affect_digest() -> None:
    context = _chain_lab()
    first = _SVC.get_neighborhood(context, ["A"], depth=1)
    second = _SVC.get_neighborhood(context, ["A"], depth=1)
    assert first.result_digest == second.result_digest
    assert first.work.assertions_evaluated == second.work.assertions_evaluated


def test_48_excluded_provenance_does_not_affect_digest() -> None:
    context, reader = _privacy_lab()
    first = _SVC.get_neighborhood(context, ["seed"], depth=1)
    hidden = reader._revisions["srcrev:hidden"]
    reader._revisions["srcrev:hidden"] = hidden.model_copy(update={"content_sha256": "f" * 64})
    second = _SVC.get_neighborhood(_rebind(context, reader), ["seed"], depth=1)
    assert first.result_digest == second.result_digest
    visible = reader._revisions["srcrev:visible"]
    reader._revisions["srcrev:visible"] = visible.model_copy(update={"content_sha256": "0" * 64})
    third = _SVC.get_neighborhood(_rebind(context, reader), ["seed"], depth=1)
    assert third.result_digest != first.result_digest


def test_49_returned_authority_changes_digest() -> None:
    context, reader = _privacy_lab()
    first = _SVC.get_neighborhood(context, ["seed"], depth=1)
    visible = reader._artifacts["src:visible"]
    reader._artifacts["src:visible"] = visible.model_copy(update={"authority": "derived"})
    second = _SVC.get_neighborhood(_rebind(context, reader), ["seed"], depth=1)
    assert second.result_digest != first.result_digest


def test_50_same_context_source_epoch_across_layers() -> None:
    context, _reader = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B"), Entity(entity_id="C")],
        assertions=[_edge("asrt:ab", "A", "B"), _edge("asrt:bc", "B", "C")],
    )
    result = _SVC.get_neighborhood(context, ["A"], depth=2)
    assert result.work.provenance_snapshot_calls == 2
    assert result.work.artifact_ids_requested == 1
    assert result.work.revision_ids_requested == 1
    assert result.work.layers[0].assertions_evaluated == 1
    assert result.work.layers[1].assertions_evaluated == 1


# --- I. Regression / scope ---


def test_51_world_public_services_unchanged() -> None:
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


def test_52_no_v43_search_api_exported() -> None:
    exported = (VNEXT_SRC / "__init__.py").read_text(encoding="utf-8")
    assert "NeighborhoodReadService" in exported
    assert "EvidenceReadService" in exported
    assert "resolve_source_anchor" not in exported
    assert "anchor_search" not in exported


def test_53_no_search_or_write_helpers_in_neighborhood_module() -> None:
    source = (VNEXT_SRC / "neighborhood.py").read_text(encoding="utf-8")
    assert "def search" not in source
    assert "publish" not in source
    assert "migration" not in source.lower()


def test_54_org_refresh_helper_still_pins_v2_epoch(
    org_context: tuple[KnowledgeReadContext, Any],
) -> None:
    context, reader = org_context
    first = _SVC.get_neighborhood(context, ["priya"], depth=1)
    refreshed = _refresh_org_context(context, reader)
    second = _SVC.get_neighborhood(refreshed, ["priya"], depth=1)
    assert first.result_digest == second.result_digest


def test_55_neighborhood_10k_benchmark_records_shape() -> None:
    if not NEIGHBORHOOD_BENCH_PATH.is_file():
        pytest.skip("neighborhood 10k artifact not yet pinned")
    payload = json.loads(NEIGHBORHOOD_BENCH_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "vnext_neighborhood_10k_v1"
    assert payload["exact_base"] == IMPLEMENTATION_BASE
    assert payload["structural_gate"]["passes"] is True
    for name in (
        "low_degree_depth_1_10k",
        "low_degree_depth_1_1k",
        "branching_depth_2_10k",
        "branching_depth_2_1k",
        "noisy_neighbor_depth_2_10k",
        "depth_boundary_depth_2_10k",
        "high_degree_depth_1_10k",
    ):
        assert name in payload["runs"]
        run = payload["runs"][name]
        assert "result_digest" in run
        assert "assertions_evaluated" in run
        assert "artifact_ids_requested" in run
    assert (
        payload["runs"]["low_degree_depth_1_10k"]["assertions_evaluated"]
        == payload["runs"]["low_degree_depth_1_1k"]["assertions_evaluated"]
    )
    branching = payload["runs"]["branching_depth_2_10k"]
    assert branching["provenance_snapshot_calls"] == 2
    assert branching["artifact_ids_requested"] == 1
    assert branching["revision_ids_requested"] == 1


@pytest.fixture(name="org_context")
def fixture_org_context() -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    return _build_from_fixture(
        "organizational_memory_v1.json",
        domain_contract=_org_domain_contract(),
        semantic_profile=_org_semantic_profile(),
        contract_digest=ORG_CONTRACT_DIGEST,
        profile_digest=ORG_PROFILE_DIGEST,
    )
