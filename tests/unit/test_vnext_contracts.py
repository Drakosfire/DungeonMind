"""V0.1 contract acceptance matrix and fixture proofs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.contracts import vnext
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext import (
    Assertion,
    AssertionMetadata,
    ContributionDisposition,
    DomainContractDescriptor,
    DomainContractRef,
    Entity,
    EntityRefValue,
    EpistemicBasis,
    EvidenceRefV3,
    IdentityAlias,
    IdentityDecisionKind,
    IdentityDecisionV3,
    KnowledgeContribution,
    KnowledgeHead,
    KnowledgeRevision,
    KnowledgeStanding,
    LabelsAllVisibility,
    LabelsAnyVisibility,
    LiteralValue,
    ProjectionRequest,
    ProjectionSnapshot,
    ProposeAssertion,
    ProposeEntity,
    ProposeIdentityDecision,
    PublicVisibility,
    PublishKnowledgeRevisionCommand,
    RetractAssertion,
    ScopeBinding,
    ScopeSelector,
    SemanticProfileDescriptorV2,
    SemanticProfilePredicate,
    SourceArtifactV3,
    SourceRevisionV2,
    SupersedeAssertion,
    TermRefValue,
    TimelessTemporalScope,
    UnknownTemporalScope,
    UtcIntervalTemporalScope,
    canonical_json,
    sha256,
)
from dungeonmind.contracts.vnext.common import DomainMetadataEntry

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "vnext"
HEX_A = "a" * 64
HEX_B = "b" * 64
NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _profile_ref() -> SemanticProfileRef:
    return SemanticProfileRef(
        profile_id="organization.memory",
        profile_revision="1",
        descriptor_sha256=HEX_A,
    )


def _domain_ref() -> DomainContractRef:
    return DomainContractRef(
        domain_id="organization.memory",
        domain_revision="1",
        descriptor_sha256=HEX_B,
    )


def _metadata(
    *,
    visibility=None,
    temporal=None,
    standing: KnowledgeStanding = KnowledgeStanding.ESTABLISHED,
    claim_mode: str = "organization:fact",
    basis: EpistemicBasis = EpistemicBasis.ASSERTED,
) -> AssertionMetadata:
    return AssertionMetadata(
        scope=[ScopeBinding(axis="organization:project", value="retrieval")],
        visibility=visibility or PublicVisibility(),
        epistemic_basis=basis,
        claim_mode=claim_mode,
        standing=standing,
        evidence_ref_ids=["evidence-1"],
        temporal_scope=temporal or TimelessTemporalScope(),
    )


def test_public_namespace_is_explicit_and_bounded() -> None:
    assert "Field" not in vnext.__all__
    assert "datetime" not in vnext.__all__
    assert "SemanticProfileRef" not in vnext.__all__
    assert len(vnext.__all__) == len(set(vnext.__all__))
    names = {model.__name__ for model in vnext.PUBLIC_CONTRACT_MODELS}
    assert names <= set(vnext.__all__)
    assert len(vnext.PUBLIC_CONTRACT_MODELS) == 17
    # Intentional inventory is explicit literals, not a dynamic globals() scrape.
    assert isinstance(vnext.__all__, list)


def test_entity_ref_assertion_round_trip() -> None:
    assertion = Assertion(
        assertion_id="a-1",
        subject_entity_id="priya",
        predicate="organization:owns",
        value=EntityRefValue(entity_id="retrieval-evaluation"),
        metadata=_metadata(),
    )
    assert Assertion.model_validate_json(assertion.model_dump_json(by_alias=True)) == assertion


def test_literal_and_term_ref_assertion_round_trips() -> None:
    literal = Assertion(
        assertion_id="a-lit",
        subject_entity_id="priya",
        predicate="organization:title",
        value=LiteralValue(value={"title": "Owner"}),
        metadata=_metadata(),
    )
    term = Assertion(
        assertion_id="a-term",
        subject_entity_id="priya",
        predicate="organization:role",
        value=TermRefValue(term="organization:lead"),
        metadata=_metadata(),
    )
    assert Assertion.model_validate_json(literal.model_dump_json(by_alias=True)) == literal
    assert Assertion.model_validate_json(term.model_dump_json(by_alias=True)) == term


@pytest.mark.parametrize(
    "visibility",
    [
        PublicVisibility(),
        LabelsAnyVisibility(labels=["organization:team"]),
        LabelsAllVisibility(labels=["organization:team", "organization:leadership"]),
    ],
)
def test_visibility_variants_round_trip(visibility) -> None:
    assertion = Assertion(
        assertion_id="a-vis",
        subject_entity_id="priya",
        predicate="organization:owns",
        value=EntityRefValue(entity_id="retrieval-evaluation"),
        metadata=_metadata(visibility=visibility),
    )
    assert Assertion.model_validate_json(assertion.model_dump_json(by_alias=True)) == assertion


def test_unknown_vs_timeless_temporal_distinction() -> None:
    unknown = Assertion(
        assertion_id="a-unk",
        subject_entity_id="priya",
        predicate="organization:owns",
        value=EntityRefValue(entity_id="x"),
        metadata=_metadata(temporal=UnknownTemporalScope()),
    )
    timeless = Assertion(
        assertion_id="a-time",
        subject_entity_id="priya",
        predicate="organization:owns",
        value=EntityRefValue(entity_id="x"),
        metadata=_metadata(temporal=TimelessTemporalScope()),
    )
    assert unknown.metadata.temporal_scope.kind == "unknown"
    assert timeless.metadata.temporal_scope.kind == "timeless"
    assert unknown.model_dump(mode="json") != timeless.model_dump(mode="json")


def test_utc_interval_json_round_trip_and_schema_shape() -> None:
    scope = UtcIntervalTemporalScope(
        valid_from=datetime(2026, 4, 1, tzinfo=UTC),
        valid_until=datetime(2026, 9, 7, tzinfo=UTC),
    )
    restored = UtcIntervalTemporalScope.model_validate_json(scope.model_dump_json())
    assert restored == scope
    assert isinstance(restored.valid_from, datetime)
    schema = UtcIntervalTemporalScope.model_json_schema()
    props = schema["properties"]
    assert props["valid_from"]["anyOf"][0]["type"] == "string"
    assert props["valid_from"]["anyOf"][0]["format"] == "date-time"


def test_utc_interval_ordering_and_required_bound() -> None:
    with pytest.raises(ValidationError):
        UtcIntervalTemporalScope()
    with pytest.raises(ValidationError):
        UtcIntervalTemporalScope(
            valid_from=datetime(2026, 9, 8, tzinfo=UTC),
            valid_until=datetime(2026, 9, 7, tzinfo=UTC),
        )


def test_scope_selector_rejects_duplicate_and_wildcard_overlap() -> None:
    with pytest.raises(ValidationError):
        ScopeSelector(
            bindings=[
                ScopeBinding(axis="organization:team", value="research"),
                ScopeBinding(axis="organization:team", value="research"),
            ]
        )
    with pytest.raises(ValidationError):
        ScopeSelector(
            bindings=[ScopeBinding(axis="organization:team", value="research")],
            wildcard_axes=["organization:team"],
        )


def test_whitespace_ids_and_non_hex_digests_fail_closed() -> None:
    with pytest.raises(ValidationError):
        Entity(entity_id="   ")
    with pytest.raises(ValidationError):
        DomainContractRef(domain_id="d", domain_revision="1", descriptor_sha256="g" * 64)
    with pytest.raises(ValidationError):
        SourceRevisionV2(
            source_revision_id="r",
            source_artifact_id="a",
            content_sha256=" " * 64,
            body_storage="inline",
            created_at=NOW,
        )


def test_canonical_json_rejection_matrix() -> None:
    with pytest.raises(ValidationError):
        LiteralValue(value={1: "bad"})  # type: ignore[dict-item]
    with pytest.raises(ValidationError):
        LiteralValue(value=float("nan"))
    with pytest.raises(ValidationError):
        DomainMetadataEntry(schema="organization:meta", payload=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        PublishKnowledgeRevisionCommand(
            space_id="space:x",
            operation_ids=["op:1"],
            graph_schema="dm_knowledge_graph_v1",
            graph_payload={"bad": object()},  # type: ignore[dict-item]
            domain_contract_ref=_domain_ref(),
            semantic_profile_ref=_profile_ref(),
            created_at=NOW,
        )


def test_domain_contract_strictness() -> None:
    descriptor = DomainContractDescriptor(
        domain_id="organization.memory",
        domain_revision="1",
        scope_axes=["organization:project"],
        visibility_labels=["organization:team"],
        claim_modes=["organization:fact"],
        admission_policy_id="policy:1",
    )
    assert (
        DomainContractDescriptor.model_validate_json(descriptor.model_dump_json()) == descriptor
    )
    with pytest.raises(ValidationError):
        DomainContractDescriptor(
            domain_id="organization.memory",
            domain_revision="1",
            scope_axes=["organization:project", "organization:project"],
            admission_policy_id="policy:1",
        )


def test_semantic_profile_predicate_value_kinds() -> None:
    profile = SemanticProfileDescriptorV2(
        profile_id="organization.memory",
        profile_revision="1",
        term_namespaces=["organization"],
        predicates=[
            SemanticProfilePredicate(
                term="organization:owns",
                allowed_value_kinds=["entity_ref"],
            )
        ],
        classification_terms=["organization:person"],
    )
    assert profile.predicates[0].allowed_value_kinds == ["entity_ref"]
    with pytest.raises(ValidationError):
        SemanticProfileDescriptorV2(
            profile_id="organization.memory",
            profile_revision="1",
            term_namespaces=["Organization"],
        )


def test_v3_open_predicate_namespace_is_explicit_and_type_constrained() -> None:
    from dungeonmind.contracts.vnext.domain import (
        OpenPredicateNamespace,
        SemanticProfileDescriptorV3,
        parse_semantic_profile_descriptor,
    )

    profile = SemanticProfileDescriptorV3(
        profile_id="organization.memory",
        profile_revision="2",
        term_namespaces=["organization", "organization.custom"],
        predicates=[
            SemanticProfilePredicate(term="organization:title", allowed_value_kinds=["literal"])
        ],
        open_predicate_namespaces=[
            OpenPredicateNamespace(
                namespace="organization.custom", allowed_value_kinds=["entity_ref"]
            )
        ],
    )
    assert parse_semantic_profile_descriptor(profile.model_dump(mode="json")) == profile
    assert profile.schema_version == "dm_semantic_profile_v3"

    with pytest.raises(ValidationError):
        SemanticProfileDescriptorV3(
            profile_id="organization.memory",
            profile_revision="2",
            term_namespaces=["organization"],
            open_predicate_namespaces=[
                OpenPredicateNamespace(
                    namespace="organization.custom", allowed_value_kinds=["entity_ref"]
                )
            ],
        )
    with pytest.raises(ValidationError):
        SemanticProfileDescriptorV3(
            profile_id="organization.memory",
            profile_revision="2",
            term_namespaces=["organization.custom"],
            open_predicate_namespaces=[
                OpenPredicateNamespace(
                    namespace="organization.custom", allowed_value_kinds=["entity_ref"]
                ),
                OpenPredicateNamespace(
                    namespace="organization.custom", allowed_value_kinds=["entity_ref"]
                ),
            ],
        )
    with pytest.raises(ValidationError):
        SemanticProfileDescriptorV3(
            profile_id="organization.memory",
            profile_revision="2",
            term_namespaces=["organization.custom"],
            predicates=[
                SemanticProfilePredicate(
                    term="organization.custom:reserved", allowed_value_kinds=["literal"]
                )
            ],
            open_predicate_namespaces=[
                OpenPredicateNamespace(
                    namespace="organization.custom", allowed_value_kinds=["entity_ref"]
                )
            ],
        )


def test_v3_semantic_profile_schema_is_checked_in() -> None:
    from scripts.generate_semantic_profile_v3_schema import main as schema_main

    assert schema_main([]) == 0


def test_source_and_evidence_are_domain_generic() -> None:
    artifact = SourceArtifactV3(
        source_artifact_id="src:doc",
        source_classification="organization:document",
        authority="primary",
        visibility=PublicVisibility(),
        status="active",
    )
    evidence = EvidenceRefV3(
        evidence_ref_id="evidence:1",
        source_artifact_id="src:doc",
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=False,
    )
    dumped = artifact.model_dump_json() + evidence.model_dump_json()
    for banned in ("world_id", "campaign", "dnd5e", "Admissibility", "GM", "PLAYER"):
        assert banned not in dumped


@pytest.mark.parametrize(
    ("kind", "subjects", "targets", "alias"),
    [
        (IdentityDecisionKind.MERGE, ["a", "b"], ["merged"], None),
        (IdentityDecisionKind.SPLIT, ["merged"], ["a", "b"], None),
        (IdentityDecisionKind.UNMERGE, ["merged"], ["a", "b"], None),
        (IdentityDecisionKind.MARK_AMBIGUOUS, ["a", "b"], [], None),
        (IdentityDecisionKind.REJECT_CANDIDATE, ["a"], [], None),
        (IdentityDecisionKind.ALIAS_ADD, ["a"], [], "Priya"),
    ],
)
def test_identity_decision_shapes(kind, subjects, targets, alias) -> None:
    decision = IdentityDecisionV3(
        decision_id="iddec:1",
        space_id="space:x",
        decision_kind=kind,
        subject_entity_ids=subjects,
        target_entity_ids=targets,
        alias=alias,
        created_at=NOW,
    )
    assert IdentityDecisionV3.model_validate_json(decision.model_dump_json()) == decision


def test_identity_decision_negative_cardinality() -> None:
    with pytest.raises(ValidationError):
        IdentityDecisionV3(
            decision_id="iddec:1",
            space_id="space:x",
            decision_kind=IdentityDecisionKind.MERGE,
            subject_entity_ids=["a"],
            target_entity_ids=["merged"],
            created_at=NOW,
        )
    with pytest.raises(ValidationError):
        IdentityDecisionV3(
            decision_id="iddec:1",
            space_id="space:x",
            decision_kind=IdentityDecisionKind.ALIAS_ADD,
            subject_entity_ids=["a"],
            created_at=NOW,
        )


def test_typed_contribution_union_and_negatives() -> None:
    contrib = KnowledgeContribution(
        contribution_id="contrib:1",
        space_id="space:x",
        producer="reviewer",
        produced_at=NOW,
        status="finalized",
        items=[
            ProposeEntity(item_id="i1", entity=Entity(entity_id="priya")),
            ProposeAssertion(
                item_id="i2",
                assertion=Assertion(
                    assertion_id="a1",
                    subject_entity_id="priya",
                    predicate="organization:owns",
                    value=EntityRefValue(entity_id="x"),
                    metadata=_metadata(),
                ),
            ),
            RetractAssertion(item_id="i3", target_assertion_id="a0"),
            SupersedeAssertion(
                item_id="i4",
                target_assertion_id="a0",
                replacement_assertion=Assertion(
                    assertion_id="a2",
                    subject_entity_id="marco",
                    predicate="organization:owns",
                    value=EntityRefValue(entity_id="x"),
                    metadata=_metadata(),
                ),
            ),
            ProposeIdentityDecision(
                item_id="i5",
                decision=IdentityDecisionV3(
                    decision_id="iddec:1",
                    space_id="space:x",
                    decision_kind=IdentityDecisionKind.REJECT_CANDIDATE,
                    subject_entity_ids=["candidate-b"],
                    created_at=NOW,
                ),
            ),
        ],
    )
    restored = KnowledgeContribution.model_validate_json(contrib.model_dump_json(by_alias=True))
    assert restored == contrib
    with pytest.raises(ValidationError):
        KnowledgeContribution(
            contribution_id="contrib:1",
            space_id="space:x",
            producer="reviewer",
            produced_at=NOW,
            status="finalized",
            items=[],
        )
    with pytest.raises(ValidationError):
        KnowledgeContribution.model_validate(
            {
                "contribution_id": "contrib:1",
                "space_id": "space:x",
                "producer": "reviewer",
                "produced_at": NOW.isoformat(),
                "status": "finalized",
                "items": [{"kind": "not_a_real_item", "item_id": "x"}],
            }
        )


def test_revision_head_and_publish_command_consistency() -> None:
    revision = KnowledgeRevision(
        space_id="space:x",
        revision_id="rev:1",
        created_at=NOW,
        operation_ids=["op:1"],
        graph_schema="dm_knowledge_graph_v1",
        graph_payload_sha256=HEX_A,
        domain_contract_ref=_domain_ref(),
        semantic_profile_ref=_profile_ref(),
    )
    head = KnowledgeHead(space_id="space:x", head_revision_id="rev:1", updated_at=NOW)
    command = PublishKnowledgeRevisionCommand(
        space_id="space:x",
        parent_revision_id=None,
        expected_parent_revision_id=None,
        operation_ids=["op:1"],
        graph_schema="dm_knowledge_graph_v1",
        graph_payload={"entities": [], "assertions": []},
        domain_contract_ref=_domain_ref(),
        semantic_profile_ref=_profile_ref(),
        created_at=NOW,
    )
    assert revision.operation_ids
    assert command.operation_ids
    with pytest.raises(ValidationError):
        PublishKnowledgeRevisionCommand(
            space_id="space:x",
            operation_ids=[],
            graph_schema="dm_knowledge_graph_v1",
            graph_payload={},
            domain_contract_ref=_domain_ref(),
            semantic_profile_ref=_profile_ref(),
            created_at=NOW,
        )
    assert KnowledgeHead.model_validate_json(head.model_dump_json()) == head


def test_projection_request_snapshot_use_closed_standing() -> None:
    request = ProjectionRequest(
        space_id="space:x",
        scope_selector=ScopeSelector(include_unscoped=True),
        standing_selector=[KnowledgeStanding.ESTABLISHED, KnowledgeStanding.PROVISIONAL],
    )
    snapshot = ProjectionSnapshot(
        space_id="space:x",
        revision_id="rev:1",
        head_revision_id="rev:1",
        is_head=True,
        domain_contract_ref=_domain_ref(),
        semantic_profile_ref=_profile_ref(),
        scope_selector=ScopeSelector(include_unscoped=True),
        standing_selector=[KnowledgeStanding.ESTABLISHED],
        projected_at=NOW,
    )
    assert ProjectionRequest.model_validate_json(request.model_dump_json()) == request
    assert ProjectionSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    with pytest.raises(ValidationError):
        ProjectionRequest.model_validate(
            {
                "space_id": "space:x",
                "scope_selector": {},
                "standing_selector": ["gm_only"],
            }
        )


def test_unknown_fields_and_malformed_terms_fail_closed() -> None:
    with pytest.raises(ValidationError):
        Assertion(
            assertion_id="a-1",
            subject_entity_id="p",
            predicate="Bad Term",
            value=EntityRefValue(entity_id="r"),
            metadata=_metadata(),
            extra="drift",  # type: ignore[call-arg]
        )


def test_organizational_memory_fixture_validates_and_has_stable_digest() -> None:
    payload = _load("organizational_memory_v1.json")
    for entity in payload["entities"]:
        Entity.model_validate(entity)
    assertions = [Assertion.model_validate(item) for item in payload["assertions"]]
    predicates = {item.predicate for item in assertions}
    assert "organization:title" in predicates
    assert "organization:classification" in predicates
    title = next(item for item in assertions if item.predicate == "organization:title")
    classification = next(
        item for item in assertions if item.predicate == "organization:classification"
    )
    assert title.value.kind == "literal"
    assert classification.value.kind == "term_ref"
    assert any(len(item.metadata.scope) == 0 for item in assertions)
    SourceArtifactV3.model_validate(payload["sources"]["artifact"])
    for revision in payload["sources"]["revisions"]:
        SourceRevisionV2.model_validate(revision)
    for evidence in payload["sources"]["evidence"]:
        EvidenceRefV3.model_validate(evidence)
    DomainContractDescriptor.model_validate(payload["domain_contract"])
    digest = sha256(canonical_json(payload))
    pinned = _load("FIXTURE_DIGESTS.json")["fixtures"]["organizational_memory_v1.json"]
    assert digest == pinned


def test_temporal_supersession_fixture_validates() -> None:
    payload = _load("temporal_supersession_v1.json")
    contrib = KnowledgeContribution.model_validate(payload["contribution"])
    assert contrib.items[0].kind == "supersede_assertion"
    for disposition in payload["dispositions"]:
        ContributionDisposition.model_validate(disposition)
    assert payload["history"][0]["owner_entity_id"] == "priya"
    assert payload["history"][1]["owner_entity_id"] == "marco"


def test_adversarial_fixture_preserves_governance_axes() -> None:
    payload = _load("adversarial_epistemic_identity_v1.json")
    assertions = [Assertion.model_validate(item) for item in payload["assertions"]]
    standings = {item.metadata.standing for item in assertions}
    bases = {item.metadata.epistemic_basis for item in assertions}
    assert KnowledgeStanding.RETRACTED in standings
    assert EpistemicBasis.SPECULATIVE in bases
    assert EpistemicBasis.ASSERTED in bases
    decisions = [IdentityDecisionV3.model_validate(item) for item in payload["identity_decisions"]]
    kinds = {item.decision_kind for item in decisions}
    assert IdentityDecisionKind.MERGE in kinds
    assert IdentityDecisionKind.SPLIT in kinds
    assert IdentityDecisionKind.UNMERGE in kinds
    assert IdentityDecisionKind.MARK_AMBIGUOUS in kinds
    assert IdentityDecisionKind.REJECT_CANDIDATE in kinds


def test_fixture_digest_ledger_is_pinned() -> None:
    pinned = _load("FIXTURE_DIGESTS.json")["fixtures"]
    actual = {
        name: sha256(canonical_json(_load(name)))
        for name in (
            "organizational_memory_v1.json",
            "temporal_supersession_v1.json",
            "adversarial_epistemic_identity_v1.json",
        )
    }
    assert actual == pinned


def test_identity_alias_round_trip() -> None:
    alias = IdentityAlias(
        alias_id="alias:1",
        entity_id="priya",
        alias_text="Priya Shah",
        standing=KnowledgeStanding.ESTABLISHED,
    )
    assert IdentityAlias.model_validate_json(alias.model_dump_json()) == alias
