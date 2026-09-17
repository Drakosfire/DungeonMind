"""Acceptance matrix for V4.2 source-anchor identity and revalidation."""

from __future__ import annotations

from dataclasses import replace

from dungeonmind.application.vnext.admission import ExcludeByAssertionIdPolicy
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.application.vnext.source_anchors import (
    build_source_anchor,
    compute_anchor_identity_digest,
    context_binding_digest,
    decode_anchor_token,
    encode_anchor_token,
)
from dungeonmind.contracts.vnext.common import KnowledgeStanding, LabelsAllVisibility, ScopeBinding
from dungeonmind.contracts.vnext.domain import Entity
from tests.unit.test_vnext_evidence_reads import (
    _SVC,
    _evidence,
    _lab_context,
    _literal,
    _rebind,
    _visible_lab,
)


def test_01_admitted_evidence_yields_deterministic_anchor() -> None:
    context, _ = _visible_lab()
    first = _SVC.get_evidence(context, "evidence:lab")
    second = _SVC.get_evidence(context, "evidence:lab")
    assert first.available is True
    assert first.anchors[0].anchor_id == second.anchors[0].anchor_id
    recovered = decode_anchor_token(first.anchors[0].anchor_id)
    assert recovered is not None
    evidence_ref_id, _digest = recovered
    assert evidence_ref_id == "evidence:lab"


def test_02_token_recovers_target_without_corpus_scan() -> None:
    from dungeonmind.application.vnext.model import ParsedKnowledgeRevision

    context, _ = _visible_lab()
    created = _SVC.get_evidence(context, "evidence:lab")
    lookup_count = {"n": 0}
    original = ParsedKnowledgeRevision.get_evidence

    def counting(self: ParsedKnowledgeRevision, evidence_ref_id: str):
        lookup_count["n"] += 1
        return original(self, evidence_ref_id)

    from unittest.mock import patch

    with patch.object(ParsedKnowledgeRevision, "get_evidence", counting):
        resolved = _SVC.resolve_source_anchor(context, created.anchors[0].anchor_id)
    assert resolved.resolved is True
    assert lookup_count["n"] < 10
    assert resolved.evidence is not None
    assert resolved.evidence.evidence_ref_id == "evidence:lab"


def test_03_false_flags_and_navigation_copied_exactly() -> None:
    context, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A", evidence_id="evidence:flags")],
        evidence=[
            _evidence(
                "evidence:flags",
                can_open_source=False,
                can_highlight_span=False,
                locator=None,
                uri=None,
                line_ref=None,
                source_span_ref_id=None,
            )
        ],
    )
    result = _SVC.get_evidence(context, "evidence:flags")
    anchor = result.anchors[0]
    assert anchor.can_open_source is False
    assert anchor.can_highlight_span is False
    assert anchor.locator is None
    assert anchor.uri is None
    assert anchor.line_ref is None
    assert anchor.source_span_ref_id is None
    assert not hasattr(anchor, "body_storage")


def test_04_context_binding_inputs_change_identity() -> None:
    from dungeonmind.domain.canonical import canonical_sha256

    context, reader = _visible_lab()
    baseline = context_binding_digest(context)
    request = context.request.model_copy(
        update={
            "scope_selector": context.request.scope_selector.model_copy(
                update={"bindings": [ScopeBinding(axis="test:scope", value="two")]}
            )
        }
    )
    changed_request = KnowledgeReadContext(
        parsed=context.parsed,
        request=request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=reader,
    )
    assert context_binding_digest(changed_request) != baseline
    contract = context.domain_contract.model_copy(update={"domain_revision": "2"})
    digest = canonical_sha256(contract.model_dump(mode="json"))
    changed_contract = KnowledgeReadContext(
        parsed=replace(
            context.parsed,
            identity=replace(
                context.parsed.identity,
                domain_contract_ref=replace(
                    context.parsed.identity.domain_contract_ref,
                    domain_revision="2",
                    descriptor_sha256=digest,
                ),
            ),
        ),
        request=context.request,
        domain_contract=contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=reader,
    )
    assert context_binding_digest(changed_contract) != baseline


def test_05_supporter_ids_are_not_anchor_identity() -> None:
    context, _ = _visible_lab()
    result = _SVC.get_evidence(context, "evidence:lab")
    assert result.evidence is not None
    first = build_source_anchor(
        context=context,
        evidence=result.evidence,
        source_artifacts=result.source_artifacts,
        source_revisions=result.source_revisions,
        admitted_supporter_assertion_ids=("asrt:a",),
    )
    second = build_source_anchor(
        context=context,
        evidence=result.evidence,
        source_artifacts=result.source_artifacts,
        source_revisions=result.source_revisions,
        admitted_supporter_assertion_ids=("asrt:a", "asrt:extra"),
    )
    assert first.anchor_id == second.anchor_id
    assert first.admitted_supporter_assertion_ids != second.admitted_supporter_assertion_ids
    digest = compute_anchor_identity_digest(
        context=context,
        evidence=result.evidence,
        source_artifacts=result.source_artifacts,
        source_revisions=result.source_revisions,
    )
    assert decode_anchor_token(first.anchor_id) == (result.evidence.evidence_ref_id, digest)


def test_06_result_digest_binds_supporter_set() -> None:
    one, _ = _visible_lab()
    two, _ = _lab_context(
        entities=[Entity(entity_id="A"), Entity(entity_id="B")],
        assertions=[
            _literal("asrt:a", "A"),
            _literal("asrt:b", "B"),
        ],
    )
    first = _SVC.get_evidence(one, "evidence:lab")
    second = _SVC.get_evidence(two, "evidence:lab")
    assert first.anchors[0].anchor_id == second.anchors[0].anchor_id
    assert first.result_digest != second.result_digest
    assert [item.assertion_id for item in second.admitted_supporter_assertions] == [
        "asrt:a",
        "asrt:b",
    ]


def test_07_valid_same_context_anchor_resolves() -> None:
    context, _ = _visible_lab()
    created = _SVC.get_evidence(context, "evidence:lab")
    resolved = _SVC.resolve_source_anchor(context, created.anchors[0].anchor_id)
    assert resolved.resolved is True
    assert resolved.anchor is not None
    assert resolved.anchor.anchor_id == created.anchors[0].anchor_id


def test_08_malformed_and_unknown_version_fail_safely() -> None:
    context, _ = _visible_lab()
    for token in ("not-an-anchor", "dm-source-anchor-v2.abc", "dm-source-anchor-v1."):
        result = _SVC.resolve_source_anchor(context, token)
        assert result.resolved is False
        assert result.anchor is None
        assert result.evidence is None
        assert result.source_artifacts == ()


def test_09_unknown_evidence_and_hidden_supporters_fail_safely() -> None:
    context, _ = _visible_lab()
    missing_token = encode_anchor_token(
        evidence_ref_id="evidence:missing", identity_digest="a" * 64
    )
    missing = _SVC.resolve_source_anchor(context, missing_token)
    assert missing.resolved is False
    hidden, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[
            _literal(
                "asrt:a",
                "A",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            )
        ],
    )
    created = _SVC.get_evidence(context, "evidence:lab")
    hidden_resolve = _SVC.resolve_source_anchor(hidden, created.anchors[0].anchor_id)
    assert hidden_resolve.resolved is False
    assert hidden_resolve.evidence is None


def test_10_request_and_policy_exclusion_fail_safely() -> None:
    context, reader = _visible_lab()
    created = _SVC.get_evidence(context, "evidence:lab")
    excluded_request = context.request.model_copy(
        update={"standing_selector": [KnowledgeStanding.RETRACTED]}
    )
    excluded_ctx = KnowledgeReadContext(
        parsed=context.parsed,
        request=excluded_request,
        domain_contract=context.domain_contract,
        semantic_profile=context.semantic_profile,
        domain_policy=context.domain_policy,
        source_reader=reader,
    )
    excluded = _SVC.resolve_source_anchor(excluded_ctx, created.anchors[0].anchor_id)
    assert excluded.resolved is False
    policy_ctx, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A")],
        policy=ExcludeByAssertionIdPolicy(
            policy_id="test.always",
            excluded_assertion_ids=frozenset({"asrt:a"}),
        ),
    )
    policy_miss = _SVC.resolve_source_anchor(policy_ctx, created.anchors[0].anchor_id)
    assert policy_miss.resolved is False


def test_11_changed_source_and_locator_invalidate_old_anchor() -> None:
    context, reader = _visible_lab()
    created = _SVC.get_evidence(context, "evidence:lab")
    artifact = reader._artifacts["src:lab"]
    reader._artifacts["src:lab"] = artifact.model_copy(update={"authority": "derived"})
    fresh = _SVC.resolve_source_anchor(_rebind(context, reader), created.anchors[0].anchor_id)
    assert fresh.resolved is False
    located, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[_literal("asrt:a", "A")],
        evidence=[_evidence("evidence:lab", locator="loc:changed")],
    )
    original, _ = _visible_lab()
    original_hit = _SVC.get_evidence(original, "evidence:lab")
    moved = _SVC.resolve_source_anchor(located, original_hit.anchors[0].anchor_id)
    assert moved.resolved is False


def test_12_manufactured_anchor_does_not_bypass_v2() -> None:
    hidden, _ = _lab_context(
        entities=[Entity(entity_id="A")],
        assertions=[
            _literal(
                "asrt:a",
                "A",
                visibility=LabelsAllVisibility(labels=["test:hidden"]),
            )
        ],
    )
    token = encode_anchor_token(evidence_ref_id="evidence:lab", identity_digest="b" * 64)
    result = _SVC.resolve_source_anchor(hidden, token)
    assert result.resolved is False
    assert result.evidence is None
    assert result.source_artifacts == ()
    assert result.anchor is None


def test_13_same_context_coherent_after_live_source_mutation() -> None:
    context, reader = _visible_lab()
    first = _SVC.get_evidence(context, "evidence:lab")
    resolved = _SVC.resolve_source_anchor(context, first.anchors[0].anchor_id)
    artifact = reader._artifacts["src:lab"]
    reader._artifacts["src:lab"] = artifact.model_copy(update={"status": "inactive"})
    still = _SVC.resolve_source_anchor(context, first.anchors[0].anchor_id)
    assert still.resolved is True
    assert still.result_digest == resolved.result_digest
    fresh = _SVC.resolve_source_anchor(_rebind(context, reader), first.anchors[0].anchor_id)
    assert fresh.resolved is False


def test_14_no_revision_only_cache_in_module() -> None:
    from pathlib import Path

    root = Path("src/dungeonmind/application/vnext")
    text = (root / "source_anchors.py").read_text()
    evidence = (root / "evidence_reads.py").read_text()
    assert "authorization_cache" not in text
    assert "global_anchor" not in evidence
