"""Acceptance matrix for V4.3 deterministic indexed search."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy, ExcludeByAssertionIdPolicy
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import SearchReadIntegrityError
from dungeonmind.application.vnext.model import ParsedKnowledgeRevision
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.records import ParsedEntity
from dungeonmind.application.vnext.search import (
    MATCH_KIND_EXACT_ID,
    MATCH_KIND_LEXICAL,
    MATCH_KIND_PREDICATE,
    MATCH_KIND_TERM_REF,
    SearchHit,
    SearchReadService,
    _capture_search_read_trace,
    _hit_sort_key,
)
from dungeonmind.application.vnext.search_normalize import (
    normalize_search_query,
    tokenize_search_text,
)
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
    TermRefValue,
)
from dungeonmind.contracts.vnext.knowledge import IdentityAlias, KnowledgeRevision
from dungeonmind.contracts.vnext.projection import ProjectionRequest
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
)

_SVC = SearchReadService()
STEWARD_PATH = REPO_ROOT / "Docs" / "Handoffs" / "HANDOFF-STEWARDSHIP-vnext-roadmap.md"
SEARCH_SRC = VNEXT_SRC / "search.py"
BUILDER_SRC = VNEXT_SRC / "builder.py"
NORMALIZE_SRC = VNEXT_SRC / "search_normalize.py"
IMPLEMENTATION_BASE = "8aa654bc192c1aeb51a5f908a44fce9a1c4c5b4c"


def _call_with_trace(operation):
    with _capture_search_read_trace() as traces:
        result = operation()
    assert traces
    return result, traces[-1]


def _lab_contract() -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.search",
        domain_revision="1",
        scope_axes=["test:scope"],
        visibility_labels=["test:audience", "test:hidden"],
        claim_modes=["test:fact"],
        admission_policy_id="test.always",
    )


def _lab_profile() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.search.profile",
        profile_revision="1",
        term_namespaces=["test", "lab"],
        predicates=[
            SemanticProfilePredicate(term="lab:title", allowed_value_kinds=["literal"]),
            SemanticProfilePredicate(term="lab:kind", allowed_value_kinds=["term_ref"]),
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
    text: str,
    *,
    evidence_id: str = "evidence:lab",
    scope_value: str = "one",
    visibility: PublicVisibility | LabelsAllVisibility | None = None,
    standing: KnowledgeStanding = KnowledgeStanding.ESTABLISHED,
    predicate: str = "lab:title",
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate=predicate,
        value=LiteralValue(value=text),
        metadata=_meta(
            evidence_id=evidence_id,
            scope_value=scope_value,
            visibility=visibility,
            standing=standing,
        ),
    )


def _term(
    assertion_id: str,
    subject: str,
    term: str = "lab:kind_active",
    *,
    evidence_id: str = "evidence:lab",
    visibility: PublicVisibility | LabelsAllVisibility | None = None,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="lab:kind",
        value=TermRefValue(term=term),
        metadata=_meta(evidence_id=evidence_id, visibility=visibility),
    )


def _evidence(
    evidence_id: str,
    artifact_id: str = "src:lab",
    revision_id: str = "srcrev:lab",
) -> EvidenceRefV3:
    return EvidenceRefV3(
        evidence_ref_id=evidence_id,
        source_artifact_id=artifact_id,
        source_revision_id=revision_id,
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=True,
        locator="loc:1",
        uri="uri:lab",
        source_locator="src-loc",
        line_ref="L1",
        source_span_ref_id="span:1",
    )


def _artifact(
    artifact_id: str = "src:lab",
    revision_id: str = "srcrev:lab",
    *,
    status: str = "active",
) -> SourceArtifactV3:
    return SourceArtifactV3(
        source_artifact_id=artifact_id,
        source_classification="test:doc",
        current_revision_id=revision_id,
        authority="primary",
        visibility=PublicVisibility(),
        status=status,
    )


def _revision(
    revision_id: str = "srcrev:lab",
    artifact_id: str = "src:lab",
) -> SourceRevisionV2:
    return SourceRevisionV2(
        source_revision_id=revision_id,
        source_artifact_id=artifact_id,
        content_sha256="c" * 64,
        body_storage="inline",
        created_at=datetime(2026, 9, 17, tzinfo=UTC),
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
        artifacts = {"src:lab": _artifact()}
    if revisions is None:
        revisions = {"srcrev:lab": _revision()}
    if evidence is None:
        evidence = [_evidence("evidence:lab")]
    revision = KnowledgeRevision(
        space_id=space_id,
        revision_id=revision_id,
        created_at=datetime(2026, 9, 17, tzinfo=UTC),
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


def _public_empty(result: Any) -> None:
    assert result.hits == ()
    dumped = str(result)
    assert "last_trace" not in dumped
    assert "structural_assertion_candidates" not in dumped
    assert "excluded" not in dumped
    assert "domain_policy" not in dumped
    assert "test:hidden" not in dumped


def _visible_lab() -> KnowledgeReadContext:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:alpha")],
        assertions=[_literal("asrt:alpha", "id:alpha", "marble vault")],
    )
    return context


def test_01_bookkeeping_records_v43_complete_v51_active() -> None:
    steward = STEWARD_PATH.read_text(encoding="utf-8")
    assert IMPLEMENTATION_BASE in steward
    assert "V4.2 COMPLETE" in steward
    assert "V4_2_EVIDENCE_SOURCE_ANCHORS_ACCEPTED" in steward
    assert "V4.3 COMPLETE" in steward
    assert "V4_3_DETERMINISTIC_INDEXED_SEARCH_ACCEPTED" in steward
    assert "V5.1 COMPLETE" in steward
    assert "V5_1_GENERIC_GOVERNED_MATERIALIZATION_ACCEPTED" in steward
    assert "V5.2 ACTIVE" in steward
    assert "BLOCKED ON V5.2" in steward


def test_02_frozen_v0_aggregate_remains_exact() -> None:
    bundle = (REPO_ROOT / "Docs" / "Contracts" / "vnext" / "dm_vnext_contract_v1.json").read_text()
    assert CANONICAL_V0_AGGREGATE in bundle


def test_03_normalization_is_shared_and_rejects_empty() -> None:
    assert normalize_search_query("  Marble Vault  ") == "marble vault"
    assert tokenize_search_text("Marble-Vault 42") == ("marble", "vault", "42")
    builder = BUILDER_SRC.read_text(encoding="utf-8")
    search = SEARCH_SRC.read_text(encoding="utf-8")
    assert "tokenize_search_text" in builder
    assert "normalize_search_query" in search
    assert "_TOKEN_PATTERN" not in builder
    context = _visible_lab()
    with pytest.raises(SearchReadIntegrityError, match="non-empty"):
        _SVC.search_entities(context, "   ")


def test_04_exact_entity_id_hit_without_scan() -> None:
    context = _visible_lab()
    result, trace = _call_with_trace(lambda: _SVC.search_entities(context, "id:alpha"))
    assert [hit.entity.entity_id for hit in result.hits] == ["id:alpha"]
    assert result.hits[0].match_kinds == (MATCH_KIND_EXACT_ID,)
    assert result.hits[0].admitted_match_assertions == ()
    assert result.hits[0].deterministic_score == 0
    assert result.completeness.status == "complete"
    assert trace.exact_id_lookups == 1
    assert trace.structural_assertion_candidates == 0
    assert trace.assertions_evaluated == 0
    assert trace.provenance_snapshot_calls == 0


def test_04b_exact_id_preserves_opaque_case() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="Entity:Alpha"), Entity(entity_id="entity:alpha")],
        assertions=[
            _literal("asrt:lower", "entity:alpha", "alpha marble"),
        ],
    )
    mixed = _SVC.search_entities(context, "Entity:Alpha")
    assert mixed.hits[0].entity.entity_id == "Entity:Alpha"
    assert mixed.hits[0].match_kinds == (MATCH_KIND_EXACT_ID,)
    assert all(
        MATCH_KIND_EXACT_ID not in hit.match_kinds
        for hit in mixed.hits
        if hit.entity.entity_id != "Entity:Alpha"
    )
    lower = _SVC.search_entities(context, "entity:alpha")
    assert lower.hits[0].entity.entity_id == "entity:alpha"
    assert MATCH_KIND_EXACT_ID in lower.hits[0].match_kinds
    assert all(hit.entity.entity_id != "Entity:Alpha" for hit in lower.hits)
    folded = _SVC.search_entities(context, "ENTITY:ALPHA")
    assert all(MATCH_KIND_EXACT_ID not in hit.match_kinds for hit in folded.hits)
    assert all(hit.entity.entity_id != "Entity:Alpha" for hit in folded.hits)


def test_04c_exact_id_does_not_trim_opaque_identity() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:alpha"), Entity(entity_id=" id:alpha")],
        assertions=[],
    )
    padded = _SVC.search_entities(context, " id:alpha")
    assert [hit.entity.entity_id for hit in padded.hits] == [" id:alpha"]
    bare = _SVC.search_entities(context, "id:alpha")
    assert [hit.entity.entity_id for hit in bare.hits] == ["id:alpha"]
    outer = _SVC.search_entities(context, "  id:alpha  ")
    assert all(MATCH_KIND_EXACT_ID not in hit.match_kinds for hit in outer.hits)


def test_05_single_lexical_token_uses_assertion_witness() -> None:
    context = _visible_lab()
    result, trace = _call_with_trace(lambda: _SVC.search_entities(context, "marble"))
    assert [hit.entity.entity_id for hit in result.hits] == ["id:alpha"]
    hit = result.hits[0]
    assert hit.match_kinds == (MATCH_KIND_LEXICAL,)
    assert [item.assertion_id for item in hit.admitted_match_assertions] == ["asrt:alpha"]
    assert trace.structural_assertion_candidates == 1
    assert trace.assertions_evaluated == 1
    assert "lexical_candidate_index" not in SEARCH_SRC.read_text(encoding="utf-8")


def test_06_multi_token_aggregates_one_hit() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:alpha")],
        assertions=[
            _literal("asrt:alpha-a", "id:alpha", "marble chamber"),
            _literal("asrt:alpha-b", "id:alpha", "obsidian vault"),
        ],
    )
    result, _trace = _call_with_trace(lambda: _SVC.search_entities(context, "marble vault"))
    assert len(result.hits) == 1
    hit = result.hits[0]
    assert hit.entity.entity_id == "id:alpha"
    assert [item.assertion_id for item in hit.admitted_match_assertions] == [
        "asrt:alpha-a",
        "asrt:alpha-b",
    ]
    assert hit.match_kinds == (MATCH_KIND_LEXICAL,)
    assert hit.deterministic_score == 22


def test_07_predicate_match_uses_predicate_index() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:alpha"), Entity(entity_id="id:beta")],
        assertions=[
            _literal("asrt:alpha", "id:alpha", "marble vault"),
            _term("asrt:beta", "id:beta"),
        ],
    )
    result, trace = _call_with_trace(lambda: _SVC.search_entities(context, "lab:title"))
    assert [hit.entity.entity_id for hit in result.hits] == ["id:alpha"]
    assert result.hits[0].match_kinds[0] == MATCH_KIND_PREDICATE
    assert [item.assertion_id for item in result.hits[0].admitted_match_assertions] == [
        "asrt:alpha"
    ]
    assert trace.structural_assertion_candidates == 1


def test_08_term_ref_match_uses_term_index() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:alpha"), Entity(entity_id="id:beta")],
        assertions=[
            _literal("asrt:alpha", "id:alpha", "marble vault"),
            _term("asrt:beta", "id:beta"),
        ],
    )
    result, trace = _call_with_trace(lambda: _SVC.search_entities(context, "lab:kind_active"))
    assert [hit.entity.entity_id for hit in result.hits] == ["id:beta"]
    assert MATCH_KIND_TERM_REF in result.hits[0].match_kinds
    assert [item.assertion_id for item in result.hits[0].admitted_match_assertions] == ["asrt:beta"]
    assert trace.structural_assertion_candidates == 1


def test_09_hidden_only_match_returns_no_public_hit() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:hidden")],
        assertions=[
            _literal(
                "asrt:hidden",
                "id:hidden",
                "marble vault",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            )
        ],
    )
    result, trace = _call_with_trace(lambda: _SVC.search_entities(context, "marble"))
    _public_empty(result)
    assert "asrt:hidden" not in str(result)
    assert "id:hidden" not in str(result)
    assert trace.structural_assertion_candidates == 1
    assert trace.admitted_match_assertions == 0
    assert not hasattr(result, "last_trace")
    assert "structural_assertion_candidates" not in result.__dataclass_fields__


def test_10_mixed_visible_hidden_same_entity_uses_visible_witness_only() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:alpha")],
        assertions=[
            _literal("asrt:visible", "id:alpha", "marble vault"),
            _literal(
                "asrt:hidden",
                "id:alpha",
                "marble vault extra",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            ),
        ],
    )
    result, _trace = _call_with_trace(lambda: _SVC.search_entities(context, "marble"))
    hit = result.hits[0]
    assert hit.entity.entity_id == "id:alpha"
    assert [item.assertion_id for item in hit.admitted_match_assertions] == ["asrt:visible"]
    assert "asrt:hidden" not in str(result)
    visible_only, _ = _lab_context(
        entities=[Entity(entity_id="id:alpha")],
        assertions=[_literal("asrt:visible", "id:alpha", "marble vault")],
    )
    control = _SVC.search_entities(visible_only, "marble")
    assert result.hits[0].deterministic_score == control.hits[0].deterministic_score
    assert result.hits[0].match_kinds == control.hits[0].match_kinds
    assert result.result_digest == control.result_digest


def test_11_hidden_high_score_decoys_do_not_consume_limit() -> None:
    assertions = [_literal("asrt:visible", "id:alpha", "obsidian flake")]
    entities = [Entity(entity_id="id:alpha")]
    for index in range(8):
        subject = f"id:decoy{index:02d}"
        entities.append(Entity(entity_id=subject))
        for copy_n in range(6):
            assertions.append(
                _literal(
                    f"asrt:decoy-{index:02d}-{copy_n}",
                    subject,
                    "obsidian flake chamber vault marble extra",
                    visibility=LabelsAllVisibility(labels=["test:hidden"]),
                )
            )
    context, _ = _lab_context(entities=entities, assertions=assertions)
    result, trace = _call_with_trace(lambda: _SVC.search_entities(context, "obsidian", limit=1))
    assert [hit.entity.entity_id for hit in result.hits] == ["id:alpha"]
    assert trace.structural_assertion_candidates > 1
    assert trace.admitted_match_assertions == 1


def test_12_excluded_matches_are_public_non_matches() -> None:
    hidden = LabelsAllVisibility(labels=["test:hidden"])
    cases = [
        _lab_context(
            entities=[Entity(entity_id="id:alpha")],
            assertions=[_literal("asrt:scope", "id:alpha", "marble vault", scope_value="two")],
        )[0],
        _lab_context(
            entities=[Entity(entity_id="id:alpha")],
            assertions=[
                _literal(
                    "asrt:standing",
                    "id:alpha",
                    "marble vault",
                    standing=KnowledgeStanding.RETRACTED,
                )
            ],
        )[0],
        _lab_context(
            entities=[Entity(entity_id="id:alpha")],
            assertions=[_literal("asrt:policy", "id:alpha", "marble vault")],
            policy=ExcludeByAssertionIdPolicy(
                policy_id="test.always",
                excluded_assertion_ids=frozenset({"asrt:policy"}),
            ),
        )[0],
        _lab_context(
            entities=[Entity(entity_id="id:alpha")],
            assertions=[
                _literal(
                    "asrt:source",
                    "id:alpha",
                    "marble vault",
                    evidence_id="evidence:dead",
                )
            ],
            evidence=[_evidence("evidence:dead", "src:dead", "srcrev:dead")],
            artifacts={"src:dead": _artifact("src:dead", "srcrev:dead", status="retracted")},
            revisions={"srcrev:dead": _revision("srcrev:dead", "src:dead")},
        )[0],
        _lab_context(
            entities=[Entity(entity_id="id:alpha")],
            assertions=[_literal("asrt:vis", "id:alpha", "marble vault", visibility=hidden)],
        )[0],
    ]
    for context in cases:
        result = _SVC.search_entities(context, "marble")
        _public_empty(result)


def test_13_deterministic_tie_breaks_by_entity_id() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:zeta"), Entity(entity_id="id:alpha")],
        assertions=[
            _literal("asrt:zeta", "id:zeta", "marble vault"),
            _literal("asrt:alpha", "id:alpha", "marble vault"),
        ],
    )
    first = _SVC.search_entities(context, "marble")
    second = _SVC.search_entities(context, "marble")
    assert [hit.entity.entity_id for hit in first.hits] == ["id:alpha", "id:zeta"]
    assert first.hits[0].deterministic_score == first.hits[1].deterministic_score
    assert first.result_digest == second.result_digest
    assert first.hits[0].match_kinds == first.hits[1].match_kinds


def test_13b_rank_classes_are_lexicographic_not_weighted_sums() -> None:
    exact = SearchHit(
        entity=ParsedEntity(entity_id="Entity:Alpha"),
        admitted_match_assertions=(),
        match_kinds=(MATCH_KIND_EXACT_ID,),
        deterministic_score=0,
    )
    predicate = SearchHit(
        entity=ParsedEntity(entity_id="id:predicate"),
        admitted_match_assertions=(),
        match_kinds=(MATCH_KIND_PREDICATE,),
        deterministic_score=1,
    )
    lexical = SearchHit(
        entity=ParsedEntity(entity_id="zzz-lex"),
        admitted_match_assertions=(),
        match_kinds=(MATCH_KIND_LEXICAL,),
        deterministic_score=2_000_000,
    )
    ordered = sorted([lexical, predicate, exact], key=_hit_sort_key)
    assert [hit.entity.entity_id for hit in ordered] == [
        "Entity:Alpha",
        "id:predicate",
        "zzz-lex",
    ]

    context, _ = _lab_context(
        entities=[
            Entity(entity_id="Entity:Alpha"),
            Entity(entity_id="zzz-lex"),
        ],
        assertions=[
            _literal("asrt:lex", "zzz-lex", "alpha alpha alpha marble vault"),
        ],
    )
    exact_result = _SVC.search_entities(context, "Entity:Alpha")
    assert [hit.entity.entity_id for hit in exact_result.hits] == ["Entity:Alpha", "zzz-lex"]
    assert exact_result.hits[0].match_kinds == (MATCH_KIND_EXACT_ID,)
    assert MATCH_KIND_LEXICAL in exact_result.hits[1].match_kinds
    assert exact_result.hits[0].deterministic_score < exact_result.hits[1].deterministic_score


def test_14_unrelated_growth_does_not_change_low_frequency_work() -> None:
    def build(decoys: int) -> KnowledgeReadContext:
        entities = [Entity(entity_id="id:alpha")]
        assertions = [_literal("asrt:alpha", "id:alpha", "marble vault")]
        for index in range(decoys):
            subject = f"id:decoy{index:04d}"
            entities.append(Entity(entity_id=subject))
            assertions.append(_literal(f"asrt:decoy-{index:04d}", subject, "unrelated filler"))
        context, _ = _lab_context(entities=entities, assertions=assertions)
        return context

    small, small_trace = _call_with_trace(lambda: _SVC.search_entities(build(20), "marble"))
    large, large_trace = _call_with_trace(lambda: _SVC.search_entities(build(400), "marble"))
    assert (
        small_trace.structural_assertion_candidates
        == large_trace.structural_assertion_candidates
        == 1
    )
    assert small_trace.assertions_evaluated == large_trace.assertions_evaluated == 1
    assert small_trace.provenance_snapshot_calls == large_trace.provenance_snapshot_calls == 1
    assert [hit.entity.entity_id for hit in small.hits] == [
        hit.entity.entity_id for hit in large.hits
    ]


def test_15_high_frequency_work_equals_real_match_set() -> None:
    def build(count: int) -> KnowledgeReadContext:
        entities = []
        assertions = []
        for index in range(count):
            subject = f"id:hit{index:03d}"
            entities.append(Entity(entity_id=subject))
            assertions.append(_literal(f"asrt:hit-{index:03d}", subject, "commonstone marker"))
        context, _ = _lab_context(entities=entities, assertions=assertions)
        return context

    small, small_trace = _call_with_trace(
        lambda: _SVC.search_entities(build(8), "commonstone", limit=8)
    )
    large, large_trace = _call_with_trace(
        lambda: _SVC.search_entities(build(40), "commonstone", limit=40)
    )
    assert small_trace.structural_assertion_candidates == 8
    assert large_trace.structural_assertion_candidates == 40
    assert large_trace.assertions_evaluated == 40
    assert len(small.hits) == 8
    assert len(large.hits) == 40


def test_16_does_not_scan_all_assertions() -> None:
    entities = [Entity(entity_id="id:alpha")]
    assertions = [_literal("asrt:alpha", "id:alpha", "marble vault")]
    for index in range(200):
        subject = f"id:noise{index:03d}"
        entities.append(Entity(entity_id=subject))
        assertions.append(_literal(f"asrt:noise-{index:03d}", subject, "unrelated filler"))
    context, _ = _lab_context(entities=entities, assertions=assertions)
    lookup_count = {"n": 0}
    original = ParsedKnowledgeRevision.get_assertion

    def counting(self: ParsedKnowledgeRevision, assertion_id: str) -> Any:
        lookup_count["n"] += 1
        return original(self, assertion_id)

    with patch.object(ParsedKnowledgeRevision, "get_assertion", counting):
        result = _SVC.search_entities(context, "marble")
    assert [hit.entity.entity_id for hit in result.hits] == ["id:alpha"]
    assert lookup_count["n"] < 40
    assert lookup_count["n"] < 200


def test_17_alias_index_is_not_authorization() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="id:alpha")],
        assertions=[_literal("asrt:alpha", "id:alpha", "unrelated filler")],
        aliases=[
            IdentityAlias(
                alias_id="al:secret",
                entity_id="id:alpha",
                alias_text="secretaliasname",
                evidence_ref_ids=["evidence:lab"],
                standing=KnowledgeStanding.ESTABLISHED,
            )
        ],
    )
    parsed = context.parsed
    assert parsed.lookup_lexical_candidates("secretaliasname") == ("id:alpha",)
    assert parsed.lookup_lexical_assertions("secretaliasname") == ()
    result = _SVC.search_entities(context, "secretaliasname")
    _public_empty(result)
    source = SEARCH_SRC.read_text(encoding="utf-8")
    assert "alias_exact_index" not in source
    assert "lookup_alias" not in source
    assert "lookup_lexical_candidates" not in source


def test_18_org_and_buddy_fixtures_share_the_engine() -> None:
    org_context, _ = _build_from_fixture(
        "organizational_memory_v1.json",
        domain_contract=_org_domain_contract(),
        semantic_profile=_org_semantic_profile(),
        contract_digest=ORG_CONTRACT_DIGEST,
        profile_digest=ORG_PROFILE_DIGEST,
    )
    org_result = _SVC.search_entities(org_context, "retrieval")
    assert "research-team" in [hit.entity.entity_id for hit in org_result.hits]
    term_result = _SVC.search_entities(org_context, "organization:project")
    assert term_result.hits
    assert MATCH_KIND_TERM_REF in term_result.hits[0].match_kinds
    id_result = _SVC.search_entities(org_context, "priya")
    assert [hit.entity.entity_id for hit in id_result.hits] == ["priya"]
    assert MATCH_KIND_EXACT_ID in id_result.hits[0].match_kinds

    buddy_context, _ = _buddy_context(_buddy_request())
    buddy_result = _SVC.search_entities(buddy_context, "dungeonbuddy:located_at")
    assert buddy_result.hits
    assert MATCH_KIND_PREDICATE in buddy_result.hits[0].match_kinds
    combined = (
        SEARCH_SRC.read_text(encoding="utf-8") + "\n" + NORMALIZE_SRC.read_text(encoding="utf-8")
    )
    for banned in ('"GM"', "'GM'", "PLAYER", "campaign_id", "NPC", "dungeonbuddy"):
        assert banned not in combined


def test_19_public_export_is_service_not_search_function() -> None:
    exported = (VNEXT_SRC / "__init__.py").read_text(encoding="utf-8")
    assert "SearchReadService" in exported
    assert "SearchResult" in exported
    assert "search(" not in exported.lower()
    assert "anchor_search" not in exported.lower()
    assert "V4_3_DETERMINISTIC_INDEXED_SEARCH_ACCEPTED" not in SEARCH_SRC.read_text(
        encoding="utf-8"
    )


def test_20_search_does_not_hydrate_complete_entities() -> None:
    context = _visible_lab()
    result = _SVC.search_entities(context, "marble")
    assert not hasattr(result.hits[0], "related_entities")
    assert "get_complete_entity" not in SEARCH_SRC.read_text(encoding="utf-8")
    assert result.completeness.reason is None
    assert result.normalized_query == "marble"
    assert result.limit == 20


def test_21_search_10k_benchmark_records_shape() -> None:
    path = REPO_ROOT / "Docs" / "Benchmarks" / "vnext_deterministic_search_10k_v1.json"
    if not path.is_file():
        pytest.skip("deterministic-search 10k artifact not yet pinned")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "vnext_deterministic_search_10k_v1"
    assert payload["exact_base"] == IMPLEMENTATION_BASE
    assert payload["structural_gate"]["passes"] is True
    for name in (
        "lexical_10k",
        "lexical_1k",
        "exact_id_10k",
        "predicate_10k",
        "term_ref_10k",
        "mixed_visible_hidden_10k",
        "hidden_decoy_ranking_10k",
        "high_frequency_10k",
    ):
        assert name in payload["runs"]
    assert (
        payload["runs"]["lexical_10k"]["structural_assertion_candidates"]
        == payload["runs"]["lexical_1k"]["structural_assertion_candidates"]
        == 1
    )
    assert payload["runs"]["high_frequency_10k"]["structural_assertion_candidates"] == 256
    assert payload["runs"]["hidden_decoy_ranking_10k"]["returned_hit_count"] == 1
