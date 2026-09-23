"""Acceptance matrix for V4.2 exact assertion/evidence support."""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy, ExcludeByAssertionIdPolicy
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import EvidenceReadIntegrityError
from dungeonmind.application.vnext.evidence_reads import (
    EvidenceReadService,
    _capture_evidence_read_trace,
)
from dungeonmind.application.vnext.model import ParsedKnowledgeRevision
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAllVisibility,
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
    LiteralValue,
    SemanticProfileDescriptorV2,
    SemanticProfilePredicate,
)
from dungeonmind.contracts.vnext.knowledge import IdentityAlias, KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.contracts.vnext.source import EvidenceRefV3, SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256
from tests.unit.test_vnext_knowledge_read_context import (
    ORG_CONTRACT_DIGEST,
    ORG_PROFILE_DIGEST,
    REPO_ROOT,
    VNEXT_SRC,
    _buddy_context,
    _buddy_request,
    _build_from_fixture,
    _org_domain_contract,
    _org_semantic_profile,
)

_SVC = EvidenceReadService()
IMPLEMENTATION_BASE = "7f5df9eace6f1ab23a0d817e0b350c379923641f"
V41_ACCEPTED = "9b0fd143552ea5e4def3f4a7c8d08050b206eb52"
V41_MERGE = "7f5df9eace6f1ab23a0d817e0b350c379923641f"
V41_REVIEW = "5230663567"
STEWARD_PATH = REPO_ROOT / "Docs" / "Handoffs" / "HANDOFF-STEWARDSHIP-vnext-roadmap.md"
V42_HANDOFF_PATH = REPO_ROOT / "Docs" / "Handoffs" / "HANDOFF-v4-2-evidence-source-anchors.md"
V41_HANDOFF_PATH = REPO_ROOT / "Docs" / "Handoffs" / "HANDOFF-v4-1-bounded-neighborhood.md"
EVIDENCE_SRC = VNEXT_SRC / "evidence_reads.py"
ANCHOR_SRC = VNEXT_SRC / "source_anchors.py"


def _call_with_trace(operation):
    with _capture_evidence_read_trace() as traces:
        result = operation()
    assert traces
    return result, traces[-1]


def _lab_contract() -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.evidence",
        domain_revision="1",
        scope_axes=["test:scope"],
        visibility_labels=["test:audience", "test:hidden"],
        claim_modes=["test:fact"],
        admission_policy_id="test.always",
    )


def _lab_profile() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.evidence.profile",
        profile_revision="1",
        term_namespaces=["test"],
        predicates=[
            SemanticProfilePredicate(term="test:title", allowed_value_kinds=["literal"]),
        ],
    )


def _meta(
    *,
    evidence_id: str = "evidence:lab",
    scope_value: str = "one",
    visibility: PublicVisibility | LabelsAllVisibility | None = None,
    standing: KnowledgeStanding = KnowledgeStanding.ESTABLISHED,
) -> AssertionMetadata:
    return AssertionMetadata(
        scope=[ScopeBinding(axis="test:scope", value=scope_value)],
        visibility=visibility or PublicVisibility(),
        epistemic_basis=EpistemicBasis.ASSERTED,
        claim_mode="test:fact",
        standing=standing,
        evidence_ref_ids=[evidence_id],
        temporal_scope=TimelessTemporalScope(),
    )


def _literal(
    assertion_id: str,
    subject: str,
    *,
    evidence_id: str = "evidence:lab",
    scope_value: str = "one",
    visibility: PublicVisibility | LabelsAllVisibility | None = None,
    standing: KnowledgeStanding = KnowledgeStanding.ESTABLISHED,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="test:title",
        value=LiteralValue(value={"n": assertion_id}),
        metadata=_meta(
            evidence_id=evidence_id,
            scope_value=scope_value,
            visibility=visibility,
            standing=standing,
        ),
    )


def _evidence(
    evidence_id: str,
    artifact_id: str = "src:lab",
    revision_id: str = "srcrev:lab",
    *,
    locator: str | None = "loc:1",
    uri: str | None = "uri:lab",
    can_open_source: bool = True,
    can_highlight_span: bool = True,
    line_ref: str | None = "L1",
    source_span_ref_id: str | None = "span:1",
) -> EvidenceRefV3:
    return EvidenceRefV3(
        evidence_ref_id=evidence_id,
        source_artifact_id=artifact_id,
        source_revision_id=revision_id,
        evidence_role="support",
        can_open_source=can_open_source,
        can_highlight_span=can_highlight_span,
        locator=locator,
        uri=uri,
        source_locator="src-loc",
        line_ref=line_ref,
        source_span_ref_id=source_span_ref_id,
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
    aliases: list[IdentityAlias] | None = None,
    artifacts: dict[str, SourceArtifactV3] | None = None,
    revisions: dict[str, SourceRevisionV2] | None = None,
    request: ProjectionRequest | None = None,
    policy: AlwaysAdmitPolicy | ExcludeByAssertionIdPolicy | None = None,
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
        evidence = [_evidence("evidence:lab")]
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
        aliases=aliases or [],
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


def _visible_lab() -> tuple[KnowledgeReadContext, InMemoryKnowledgeSourceReader]:
    return _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A")],
    )


def _public_unavailable(result: Any) -> None:
    assert result.available is False
    assert getattr(result, "assertion", None) is None
    assert getattr(result, "evidence", None) in (None, ())
    if getattr(result, "admitted_supporter_assertions", None) is not None:
        assert result.admitted_supporter_assertions == ()
    assert result.source_artifacts == ()
    assert result.source_revisions == ()
    assert result.anchors == ()
    dumped = str(result)
    assert "src:lab" not in dumped
    assert "loc:1" not in dumped
    assert "uri:lab" not in dumped
    assert "span:1" not in dumped
    assert "domain_policy" not in dumped
    assert "hidden" not in dumped.lower() or "test:hidden" not in dumped


def test_01_bookkeeping_records_v41_complete() -> None:
    steward = STEWARD_PATH.read_text(encoding="utf-8")
    handoff = V42_HANDOFF_PATH.read_text(encoding="utf-8")
    v41 = V41_HANDOFF_PATH.read_text(encoding="utf-8")
    assert IMPLEMENTATION_BASE in steward
    assert V41_ACCEPTED in steward
    assert V41_MERGE in steward
    assert V41_REVIEW in steward
    assert "V4_1_BOUNDED_NEIGHBORHOOD_ACCEPTED" in steward
    assert "V4.1 COMPLETE" in steward
    assert "V4.2 COMPLETE" in steward
    assert "V5.1 COMPLETE" in steward
    assert "V5.2 COMPLETE" in steward
    assert "V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED" in handoff
    assert v41.split("**Status:**", 1)[1].startswith(" COMPLETE")
    assert handoff.split("**Status:**", 1)[1].startswith(" COMPLETE")


def test_02_admitted_assertion_returns_exact_evidence() -> None:
    context, _ = _visible_lab()
    result = _SVC.get_assertion_evidence(context, "asrt:a")
    assert result.available is True
    assert result.assertion is not None
    assert result.assertion.assertion_id == "asrt:a"
    assert [item.evidence_ref_id for item in result.evidence] == ["evidence:lab"]
    assert len(result.anchors) == 1
    assert result.anchors[0].evidence_ref_id == "evidence:lab"


def test_03_admitted_assertion_with_zero_evidence_is_valid() -> None:
    assertion = _literal("asrt:empty", "A")
    assertion = assertion.model_copy(
        update={"metadata": assertion.metadata.model_copy(update={"evidence_ref_ids": []})}
    )
    context, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[assertion],
        evidence=[],
    )
    result = _SVC.get_assertion_evidence(context, "asrt:empty")
    assert result.available is True
    assert result.evidence == ()
    assert result.anchors == ()


def test_04_missing_and_hidden_assertion_share_unavailable_shape() -> None:
    missing_ctx, _ = _lab_context(entities=[Entity(entity_id="A")], assertions=[], evidence=[])
    hidden_ctx, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[
            _literal(
                "asrt:hidden",
                "A",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            )
        ],
    )
    missing = _SVC.get_assertion_evidence(missing_ctx, "asrt:hidden")
    hidden = _SVC.get_assertion_evidence(hidden_ctx, "asrt:hidden")
    _public_unavailable(missing)
    _public_unavailable(hidden)
    assert missing.result_digest == hidden.result_digest


def test_05_out_of_scope_standing_and_policy_expose_nothing() -> None:
    scoped, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A", scope_value="two")],
    )
    standing, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A", standing=KnowledgeStanding.PROVISIONAL)],
    )
    policy_ctx, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A")],
        policy=ExcludeByAssertionIdPolicy(
            policy_id="test.always",
            excluded_assertion_ids=frozenset({"asrt:a"}),
        ),
    )
    for context in (scoped, standing, policy_ctx):
        result = _SVC.get_assertion_evidence(context, "asrt:a")
        _public_unavailable(result)


def test_06_inactive_source_preserves_fail_closed() -> None:
    context, reader = _visible_lab()
    artifact = reader._artifacts["src:lab"]
    reader._artifacts["src:lab"] = artifact.model_copy(update={"status": "inactive"})
    result = _SVC.get_assertion_evidence(_rebind(context, reader), "asrt:a")
    _public_unavailable(result)


def test_07_no_alias_or_search_fallback() -> None:
    context, _ = _visible_lab()
    with pytest.raises(EvidenceReadIntegrityError):
        _SVC.get_assertion_evidence(context, "")
    source = EVIDENCE_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)]
    assert "lookup_alias" not in calls
    assert "lookup_lexical_candidates" not in calls


def test_08_repeated_read_is_deterministic_and_ordered() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[
            Assertion(
                assertion_id="asrt:multi",
                subject_entity_id="A",
                predicate="test:title",
                value=LiteralValue(value={"n": "multi"}),
                metadata=_meta(evidence_id="evidence:b").model_copy(
                    update={"evidence_ref_ids": ["evidence:b", "evidence:a"]}
                ),
            )
        ],
        evidence=[
            _evidence("evidence:b", locator="b"),
            _evidence("evidence:a", locator="a"),
        ],
    )
    first = _SVC.get_assertion_evidence(context, "asrt:multi")
    second = _SVC.get_assertion_evidence(context, "asrt:multi")
    assert first == second
    assert [item.evidence_ref_id for item in first.evidence] == ["evidence:a", "evidence:b"]
    assert [item.anchor_id for item in first.anchors] == [item.anchor_id for item in second.anchors]


def test_09_one_admitted_supporter_returns_target_evidence() -> None:
    context, _ = _visible_lab()
    result = _SVC.get_evidence(context, "evidence:lab")
    assert result.available is True
    assert result.evidence is not None
    assert result.evidence.evidence_ref_id == "evidence:lab"
    assert [item.assertion_id for item in result.admitted_supporter_assertions] == ["asrt:a"]
    assert len(result.anchors) == 1


def test_10_missing_zero_supporter_and_alias_only_are_unavailable() -> None:
    missing_ctx, _ = _visible_lab()
    missing = _SVC.get_evidence(missing_ctx, "evidence:missing")
    _public_unavailable(missing)
    assert missing.available is False

    alias_ctx, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[],
        aliases=[
            IdentityAlias(
                alias_id="al:a",
                entity_id="A",
                alias_text="Alias",
                evidence_ref_ids=["evidence:alias"],
                standing=KnowledgeStanding.ESTABLISHED,
            )
        ],
        evidence=[_evidence("evidence:alias")],
    )
    lookup_count = {"n": 0}
    original = ParsedKnowledgeRevision.get_alias

    def counting(self: ParsedKnowledgeRevision, alias_id: str) -> Any:
        lookup_count["n"] += 1
        return original(self, alias_id)

    with patch.object(ParsedKnowledgeRevision, "get_alias", counting):
        alias_only, trace = _call_with_trace(lambda: _SVC.get_evidence(alias_ctx, "evidence:alias"))
    _public_unavailable(alias_only)
    assert lookup_count["n"] == 0
    assert "orphan" not in str(alias_only).lower()
    assert trace.supporter_candidates == 0


def test_11_hidden_scope_and_policy_only_supporters_unavailable() -> None:
    hidden, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[
            _literal(
                "asrt:hidden",
                "A",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            )
        ],
    )
    scoped, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A", scope_value="two")],
    )
    policy_ctx, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A")],
        policy=ExcludeByAssertionIdPolicy(
            policy_id="test.always",
            excluded_assertion_ids=frozenset({"asrt:a"}),
        ),
    )
    for context in (hidden, scoped, policy_ctx):
        result = _SVC.get_evidence(context, "evidence:lab")
        _public_unavailable(result)


def test_12_mixed_visibility_returns_only_admitted_supporters() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[
            _literal("asrt:visible", "A", evidence_id="evidence:shared"),
            _literal(
                "asrt:hidden",
                "B",
                evidence_id="evidence:shared",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            ),
            _literal("asrt:other", "A", evidence_id="evidence:other"),
        ],
        evidence=[_evidence("evidence:shared"), _evidence("evidence:other")],
    )
    result = _SVC.get_evidence(context, "evidence:shared")
    assert result.available is True
    assert [item.assertion_id for item in result.admitted_supporter_assertions] == ["asrt:visible"]
    assert result.evidence is not None
    assert result.evidence.evidence_ref_id == "evidence:shared"
    returned_ids = {item.evidence_ref_id for item in (result.evidence,)}
    assert "evidence:other" not in returned_ids
    assert "asrt:hidden" not in str(result)


def test_13_exact_lookup_uses_evidence_supporters_not_all_assertions() -> None:
    entities = [Entity(entity_id="A")]
    assertions = [_literal("asrt:a", "A")]
    for index in range(50):
        entities.append(Entity(entity_id=f"decoy-{index:02d}"))
        assertions.append(
            _literal(
                f"asrt:decoy-{index:02d}",
                f"decoy-{index:02d}",
                evidence_id="evidence:decoy",
            )
        )
    context, _ = _lab_context(
        entities=entities,
        assertions=assertions,
        evidence=[_evidence("evidence:lab"), _evidence("evidence:decoy")],
    )
    lookup_count = {"n": 0}
    original = ParsedKnowledgeRevision.get_assertion

    def counting(self: ParsedKnowledgeRevision, assertion_id: str) -> Any:
        lookup_count["n"] += 1
        return original(self, assertion_id)

    with patch.object(ParsedKnowledgeRevision, "get_assertion", counting):
        result, trace = _call_with_trace(lambda: _SVC.get_evidence(context, "evidence:lab"))
    assert result.available is True
    assert lookup_count["n"] < 20
    assert trace.supporter_candidates == 1
    assert not hasattr(result, "supporter_candidates")
    assert not hasattr(result, "work")


def test_14_public_dto_omits_raw_candidate_counts() -> None:
    hidden, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[
            _literal(
                "asrt:hidden",
                "A",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            )
        ],
    )
    result, hidden_trace = _call_with_trace(lambda: _SVC.get_evidence(hidden, "evidence:lab"))
    assert hidden_trace.supporter_candidates == 1
    assert "supporter_candidates" not in result.__dataclass_fields__
    missing, _ = _lab_context(entities=[Entity(entity_id="A")], assertions=[], evidence=[])
    missing_result = _SVC.get_evidence(missing, "evidence:lab")
    assert result.result_digest == missing_result.result_digest
    assert not hasattr(_SVC, "last_trace")
    assert "last_trace" not in dir(_SVC)


def test_15_unrelated_growth_does_not_change_fixed_target_work() -> None:
    def build(decoys: int) -> KnowledgeReadContext:
        entities = [Entity(entity_id="A")]
        assertions = [_literal("asrt:a", "A")]
        evidence = [_evidence("evidence:lab")]
        for index in range(decoys):
            entities.append(Entity(entity_id=f"decoy-{index:04d}"))
            assertions.append(
                _literal(
                    f"asrt:decoy-{index:04d}",
                    f"decoy-{index:04d}",
                    evidence_id=f"evidence:decoy-{index:04d}",
                )
            )
            evidence.append(_evidence(f"evidence:decoy-{index:04d}"))
        context, _ = _lab_context(entities=entities, assertions=assertions, evidence=evidence)
        return context

    small, small_trace = _call_with_trace(lambda: _SVC.get_evidence(build(20), "evidence:lab"))
    large, large_trace = _call_with_trace(lambda: _SVC.get_evidence(build(400), "evidence:lab"))
    assert small_trace.supporter_candidates == large_trace.supporter_candidates == 1
    assert small_trace.assertions_evaluated == large_trace.assertions_evaluated == 1
    assert small_trace.unique_artifact_ids_requested == large_trace.unique_artifact_ids_requested
    assert small.available is large.available is True


def test_16_high_support_scales_honestly() -> None:
    def build(count: int) -> KnowledgeReadContext:
        entities = [Entity(entity_id=f"e{index:03d}") for index in range(count)]
        assertions = [
            _literal(f"asrt:{index:03d}", f"e{index:03d}", evidence_id="evidence:hub")
            for index in range(count)
        ]
        context, _ = _lab_context(
            entities=entities,
            assertions=assertions,
            evidence=[_evidence("evidence:hub")],
        )
        return context

    four, four_trace = _call_with_trace(lambda: _SVC.get_evidence(build(4), "evidence:hub"))
    many, many_trace = _call_with_trace(lambda: _SVC.get_evidence(build(64), "evidence:hub"))
    assert four.available is many.available is True
    assert four_trace.supporter_candidates == 4
    assert many_trace.supporter_candidates == 64
    assert len(many.admitted_supporter_assertions) == 64


def test_17_org_and_buddy_fixtures_use_generic_engine() -> None:
    org_ctx, _ = _build_from_fixture(
        "organizational_memory_v1.json",
        domain_contract=_org_domain_contract(),
        semantic_profile=_org_semantic_profile(),
        contract_digest=ORG_CONTRACT_DIGEST,
        profile_digest=ORG_PROFILE_DIGEST,
    )
    org_assertion_ids = tuple(org_ctx.parsed.assertions_by_id)
    assert org_assertion_ids
    org_result = _SVC.get_assertion_evidence(org_ctx, org_assertion_ids[0])
    assert org_result.completeness.status == "complete"
    buddy_ctx, _ = _buddy_context(_buddy_request(campaign="C2"))
    buddy_result = _SVC.get_assertion_evidence(buddy_ctx, "asrt:c2-player-fact")
    assert buddy_result.available is True
    combined = EVIDENCE_SRC.read_text(encoding="utf-8") + "\n"
    combined += ANCHOR_SRC.read_text(encoding="utf-8")
    for banned in ('"GM"', "'GM'", "PLAYER", "campaign_id", "NPC", "dungeonbuddy"):
        assert banned not in combined


def test_18_no_v43_search_or_body_fetch() -> None:
    source = EVIDENCE_SRC.read_text(encoding="utf-8") + ANCHOR_SRC.read_text(encoding="utf-8")
    assert "def search" not in source
    assert "body_storage" not in source
    assert "anchor_search" not in source
    from tests.unit.test_vnext_knowledge_read_context import CANONICAL_V0_AGGREGATE as frozen

    bundle = (REPO_ROOT / "Docs" / "Contracts" / "vnext" / "dm_vnext_contract_v1.json").read_text()
    assert frozen in bundle


def test_19_evidence_support_10k_benchmark_records_shape() -> None:
    path = REPO_ROOT / "Docs" / "Benchmarks" / "vnext_evidence_support_10k_v1.json"
    if not path.is_file():
        pytest.skip("evidence-support 10k artifact not yet pinned")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "vnext_evidence_support_10k_v1"
    assert payload["exact_base"] == IMPLEMENTATION_BASE
    assert payload["structural_gate"]["passes"] is True
    for name in (
        "assertion_support_10k",
        "assertion_support_1k",
        "evidence_support_10k",
        "evidence_support_1k",
        "high_support_4",
        "high_support_64",
        "high_support_256",
        "anchor_revalidation_10k",
        "anchor_revalidation_1k",
        "privacy_visible",
        "privacy_hidden_only",
        "privacy_mixed",
    ):
        assert name in payload["runs"]
        run = payload["runs"][name]
        assert "result_digest" in run
        assert "supporter_candidates" in run
        assert "assertions_evaluated" in run
        assert "unique_artifact_ids_requested" in run


def test_20_exported_service_has_no_hidden_candidate_side_channel() -> None:
    hidden, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[
            _literal(
                "asrt:hidden",
                "A",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            )
        ],
    )
    missing, _ = _lab_context(entities=[Entity(entity_id="A")], assertions=[], evidence=[])
    service = EvidenceReadService()
    hidden_result = service.get_evidence(hidden, "evidence:lab")
    missing_result = service.get_evidence(missing, "evidence:lab")
    assert hidden_result.available is False
    assert missing_result.available is False
    assert hidden_result.result_digest == missing_result.result_digest
    assert not hasattr(service, "last_trace")
    assert "last_trace" not in dir(service)
    exported = (VNEXT_SRC / "__init__.py").read_text(encoding="utf-8")
    assert "last_trace" not in exported
    assert "EvidenceReadTrace" not in exported
    assert "_capture_evidence_read_trace" not in exported
    _, hidden_trace = _call_with_trace(lambda: service.get_evidence(hidden, "evidence:lab"))
    _, missing_trace = _call_with_trace(lambda: service.get_evidence(missing, "evidence:lab"))
    assert hidden_trace.supporter_candidates == 1
    assert missing_trace.supporter_candidates == 0


def test_21_get_evidence_hoists_admitted_supporter_set() -> None:
    source = EVIDENCE_SRC.read_text(encoding="utf-8")
    assert "admitted_id_set = set(admission.admitted_assertion_ids)" in source
    assert "if assertion_id in set(admission.admitted_assertion_ids)" not in source
    tree = ast.parse(source)
    service_cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "EvidenceReadService"
    )
    method = next(
        node
        for node in service_cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_evidence"
    )
    nested_set_in_comp = [
        node
        for node in ast.walk(method)
        if isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp))
        for inner in ast.walk(node)
        if (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "set"
        )
    ]
    assert nested_set_in_comp == []
