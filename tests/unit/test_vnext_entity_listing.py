"""Scoped unseeded listing at Core's actual admission/source boundary."""

from dataclasses import FrozenInstanceError, asdict, replace
from unittest.mock import patch

import pytest

from dungeonmind.application.vnext import EntityListResult, EntityReadService
from dungeonmind.application.vnext.admission import ExcludeByAssertionIdPolicy
from dungeonmind.application.vnext.errors import EntityReadIntegrityError
from dungeonmind.application.vnext.frozen_json import FrozenDict
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.vnext.common import (
    KnowledgeStanding,
    LabelsAnyVisibility,
    ScopeBinding,
    ScopeSelector,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    Entity,
    EntityRefValue,
    LiteralValue,
)
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from tests.unit.test_vnext_entity_reads import _lab_context

SVC = EntityReadService()


def assertion(identifier="a:visible", subject="ent:source", target=None, **meta):
    return Assertion(
        assertion_id=identifier,
        subject_entity_id=subject,
        predicate="test:relates" if target else "test:title",
        value=EntityRefValue(entity_id=target)
        if target
        else LiteralValue(value="Exact source claim"),
        metadata=AssertionMetadata(
            **{
                "scope": [ScopeBinding(axis="test:scope", value="one")],
                "visibility": {"kind": "public"},
                "epistemic_basis": "asserted",
                "claim_mode": "test:fact",
                "standing": "established",
                "evidence_ref_ids": ["ev:one"],
                "temporal_scope": {"kind": "unknown"},
                **meta,
            }
        ),
    )


def context(rows=None, entities=None, **kwargs):
    if rows is None:
        rows = [assertion(target="ent:incoming-only")]
    if entities is None:
        entities = ["ent:source", "ent:incoming-only", "ent:orphan"]
    return _lab_context(
        entities=[Entity(entity_id=identifier) for identifier in entities],
        assertions=rows,
        evidence=[
            EvidenceRefV3(
                evidence_ref_id="ev:one",
                source_artifact_id="src:lab",
                source_revision_id="srcrev:lab",
                evidence_role="support",
                can_open_source=True,
                can_highlight_span=False,
                locator="line:1",
            )
        ],
        **kwargs,
    )[0]


def adjusted(ctx, *, request=None, policy=None, parsed=None, reader=None):
    return KnowledgeReadContext(
        parsed=parsed or ctx.parsed,
        request=request or ctx.request,
        domain_contract=ctx.domain_contract,
        semantic_profile=ctx.semantic_profile,
        domain_policy=policy or ctx.domain_policy,
        source_reader=reader or ctx.source_reader,
    )


def ids(result):
    return tuple(entity.entity_id for entity in result.entities)


def test_complete_listing_includes_incoming_only_endpoint_not_orphan():
    ctx = context()
    result = SVC.list_entities(ctx)
    assert isinstance(result, EntityListResult)
    assert ids(result) == ("ent:incoming-only", "ent:source")
    assert result.admitted_assertion_ids == ("a:visible",)
    assert result.identity == ctx.parsed.identity
    assert result.completeness.status == "complete"
    # Presence is not an endpoint fact grant.
    assert SVC.get_entity(ctx, "ent:incoming-only").assertions == ()


def test_no_search_limit_and_one_admission_pass():
    names = [f"ent:{i:03}" for i in range(63)]
    ctx = context([assertion(f"a:{i}", subject=n) for i, n in enumerate(names)], names)
    original = KnowledgeReadContext.evaluate_candidates
    with patch.object(
        KnowledgeReadContext, "evaluate_candidates", autospec=True, side_effect=original
    ) as admission:
        result = SVC.list_entities(ctx)
    assert ids(result) == tuple(names)
    assert len(result.admitted_assertion_ids) == 63
    assert admission.call_count == 1


@pytest.mark.parametrize("gate", ["scope", "audience", "standing", "domain", "source"])
def test_denied_relationship_does_not_introduce_either_endpoint(gate):
    metadata = {}
    if gate == "scope":
        metadata["scope"] = [ScopeBinding(axis="test:scope", value="two")]
    elif gate == "audience":
        metadata["visibility"] = LabelsAnyVisibility(labels=["test:audience"])
    elif gate == "standing":
        metadata["standing"] = KnowledgeStanding.PROVISIONAL
    ctx = context([assertion(target="ent:incoming-only", **metadata)])
    if gate == "audience":
        ctx = adjusted(ctx, request=ctx.request.model_copy(update={"audience_labels": []}))
    elif gate == "domain":
        ctx = adjusted(
            ctx,
            policy=ExcludeByAssertionIdPolicy(
                policy_id=ctx.domain_policy.policy_id,
                excluded_assertion_ids=frozenset({"a:visible"}),
            ),
        )
    elif gate == "source":
        _, reader = _lab_context(entities=[], assertions=[], evidence=[])
        reader._artifacts["src:lab"] = reader._artifacts["src:lab"].model_copy(
            update={"status": "retracted"}
        )
        ctx = adjusted(ctx, reader=reader)
    result = SVC.list_entities(ctx)
    assert ids(result) == result.admitted_assertion_ids == ()
    assert result.completeness.status == "complete"
    assert "ent:incoming-only" not in str(asdict(result))


def test_independent_admitted_presence_survives_a_denied_edge():
    ctx = context(
        [
            assertion(
                target="ent:incoming-only", scope=[ScopeBinding(axis="test:scope", value="two")]
            ),
            assertion("a:own", subject="ent:incoming-only"),
        ]
    )
    result = SVC.list_entities(ctx)
    assert ids(result) == ("ent:incoming-only",)
    assert result.admitted_assertion_ids == ("a:own",)


def test_empty_and_identity_only_revision_are_complete_empty():
    assert SVC.list_entities(context([], [])).entities == ()
    result = SVC.list_entities(context([], ["ent:known"]))
    assert result.entities == result.admitted_assertion_ids == ()
    assert result.completeness.status == "complete"


def test_digest_stable_but_commits_to_exact_request():
    ctx = context()
    result = SVC.list_entities(ctx)
    assert SVC.list_entities(ctx) == result
    request = ctx.request.model_copy(
        update={
            "scope_selector": ScopeSelector(
                include_unscoped=True,
                bindings=[
                    ScopeBinding(axis="test:scope", value="one"),
                    ScopeBinding(axis="test:scope", value="two"),
                ],
            )
        }
    )
    other = SVC.list_entities(adjusted(ctx, request=request))
    assert ids(other) == ids(result)
    assert other.request_sha256 != result.request_sha256
    assert other.result_digest != result.result_digest


def test_hidden_only_addition_under_same_test_pins_does_not_change_public_result():
    policy = ExcludeByAssertionIdPolicy(
        policy_id="test.always", excluded_assertion_ids=frozenset({"a:hidden"})
    )
    before = context([assertion()], ["ent:source"], policy=policy)
    after = context(
        [assertion(), assertion("a:hidden", subject="ent:hidden")],
        ["ent:source", "ent:hidden"],
        policy=policy,
    )
    result = SVC.list_entities(before)
    assert SVC.list_entities(after) == result
    packet = asdict(result)
    assert "ent:hidden" not in str(packet) and "a:hidden" not in str(packet)
    assert not {"work", "excluded", "candidate_count"} & set(packet)


@pytest.mark.parametrize("missing", ["ent:source", "ent:incoming-only"])
def test_dangling_admitted_endpoint_fails_integrity(missing):
    ctx = context()
    parsed = replace(
        ctx.parsed,
        entities_by_id=FrozenDict(
            {k: v for k, v in ctx.parsed.entities_by_id.items() if k != missing}
        ),
    )
    with pytest.raises(EntityReadIntegrityError, match="listing endpoint missing"):
        SVC.list_entities(adjusted(ctx, parsed=parsed))


def test_missing_admitted_assertion_fails_integrity():
    ctx = context()
    admitted = ctx.evaluate_candidates(("a:visible",))
    parsed = replace(ctx.parsed, assertions_by_id=FrozenDict())
    with (
        patch.object(KnowledgeReadContext, "evaluate_candidates", return_value=admitted),
        pytest.raises(EntityReadIntegrityError, match="listing assertion missing"),
    ):
        SVC.list_entities(adjusted(ctx, parsed=parsed))


def test_result_is_immutable_and_preserves_self_loop_identity():
    result = SVC.list_entities(context([assertion(target="ent:source")]))
    assert ids(result) == ("ent:source",)
    with pytest.raises(FrozenInstanceError):
        result.entities = ()
