"""Acceptance matrix for V5.1 generic governed materialization."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import GovernedMaterializationIntegrityError
from dungeonmind.application.vnext.materialization import (
    NATIVE_VNEXT_GRAPH_SCHEMA,
    GovernedPublicationIdentity,
    decode_native_graph_payload,
    materialize_governed_revision,
)
from dungeonmind.application.vnext.model import ParsedKnowledgeRevision
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    DomainMetadataEntry,
    DomainTemporalScope,
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAnyVisibility,
    PublicVisibility,
    ScopeBinding,
    TimelessTemporalScope,
)
from dungeonmind.contracts.vnext.contribution import (
    ContributionDisposition,
    KnowledgeContribution,
    ProposeAssertion,
    ProposeEntity,
    ProposeIdentityDecision,
    RetractAssertion,
    SupersedeAssertion,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractDescriptor,
    DomainContractRef,
    Entity,
    EntityRefValue,
    LiteralValue,
    OpenPredicateNamespace,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
    SemanticProfilePredicate,
)
from dungeonmind.contracts.vnext.knowledge import (
    IdentityAlias,
    IdentityDecisionKind,
    IdentityDecisionStatus,
    IdentityDecisionV3,
    KnowledgeRevision,
    PublishKnowledgeRevisionCommand,
)
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.canonical import canonical_sha256
from tests.unit.test_vnext_knowledge_read_context import (
    CANONICAL_V0_AGGREGATE,
    FIXTURES_DIR,
    ORG_CONTRACT_DIGEST,
    ORG_PROFILE_DIGEST,
    REPO_ROOT,
    VNEXT_SRC,
    _buddy_context,
    _buddy_domain_contract,
    _buddy_request,
    _buddy_semantic_profile,
    _build_from_fixture,
    _org_domain_contract,
    _org_semantic_profile,
)

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
MATERIALIZATION_SRC = VNEXT_SRC / "materialization.py"
IMPLEMENTATION_BASE = "bc115eb40f1601e5b6c6fda23ff05ee5bf06883d"


def _meta(evidence_id: str = "ev:lab") -> AssertionMetadata:
    return AssertionMetadata(
        scope=[ScopeBinding(axis="lab:scope", value="one")],
        visibility=PublicVisibility(),
        epistemic_basis=EpistemicBasis.ASSERTED,
        claim_mode="lab:fact",
        standing=KnowledgeStanding.ESTABLISHED,
        evidence_ref_ids=[evidence_id],
        temporal_scope=TimelessTemporalScope(),
    )


def _literal(
    assertion_id: str,
    subject: str,
    text: str,
    *,
    evidence_id: str = "ev:lab",
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject_entity_id=subject,
        predicate="lab:title",
        value=LiteralValue(value=text),
        metadata=_meta(evidence_id),
    )


def _evidence(evidence_id: str = "ev:lab") -> EvidenceRefV3:
    return EvidenceRefV3(
        evidence_ref_id=evidence_id,
        source_artifact_id="art:lab",
        source_revision_id="srcrev:lab",
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=False,
    )


def _lab_descriptors() -> tuple[DomainContractDescriptor, SemanticProfileDescriptorV2]:
    contract = DomainContractDescriptor(
        domain_id="lab.domain",
        domain_revision="1",
        scope_axes=["lab:scope"],
        visibility_labels=["lab:hidden"],
        claim_modes=["lab:fact"],
        admission_policy_id="lab.always",
    )
    profile = SemanticProfileDescriptorV2(
        profile_id="lab.profile",
        profile_revision="1",
        term_namespaces=["lab"],
        predicates=[
            SemanticProfilePredicate(term="lab:title", allowed_value_kinds=["literal"]),
            SemanticProfilePredicate(term="lab:reports_to", allowed_value_kinds=["entity_ref"]),
        ],
    )
    return contract, profile


def _lab_digests() -> tuple[str, str]:
    contract, profile = _lab_descriptors()
    return (
        canonical_sha256(contract.model_dump(mode="json")),
        canonical_sha256(profile.model_dump(mode="json")),
    )


_materialize = materialize_governed_revision


def _call(**kwargs):
    parent = kwargs["parent"]
    contract, profile = _lab_descriptors()
    kwargs.setdefault("publication", _publication(parent))
    kwargs.setdefault("domain_contract", contract)
    kwargs.setdefault("semantic_profile", profile)
    return _materialize(**kwargs)


def _parent(
    *,
    entities: list[Entity] | None = None,
    assertions: list[Assertion] | None = None,
    aliases: list[IdentityAlias] | None = None,
    evidence: list[EvidenceRefV3] | None = None,
    space_id: str = "space:lab",
    revision_id: str = "rev:parent",
    graph_schema: str = NATIVE_VNEXT_GRAPH_SCHEMA,
    profile: SemanticProfileDescriptorV2 | None = None,
) -> ParsedKnowledgeRevision:
    if entities is None:
        entities = [Entity(entity_id="ent:alice")]
    if assertions is None:
        assertions = [_literal("asrt:alice-title", "ent:alice", "Alice")]
    if evidence is None:
        evidence = [_evidence()]
    contract_digest, profile_digest = _lab_digests()
    if profile is not None:
        profile_digest = canonical_sha256(profile.model_dump(mode="json"))
    revision = KnowledgeRevision(
        space_id=space_id,
        revision_id=revision_id,
        created_at=NOW,
        operation_ids=["op:parent"],
        graph_schema=graph_schema,
        graph_payload_sha256="0" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id="lab.domain",
            domain_revision="1",
            descriptor_sha256=contract_digest,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id=profile.profile_id if profile else "lab.profile",
            profile_revision=profile.profile_revision if profile else "1",
            descriptor_sha256=profile_digest,
        ),
    )
    return build_parsed_knowledge_revision(
        revision=revision,
        entities=entities,
        assertions=assertions,
        aliases=aliases or [],
        evidence=evidence,
    )


def _publication(parent: ParsedKnowledgeRevision) -> GovernedPublicationIdentity:
    return GovernedPublicationIdentity(
        operation_ids=("op:child",),
        created_at=NOW,
        expected_parent_revision_id=parent.revision_id,
    )


def _accepted(*item_ids: str) -> list[ContributionDisposition]:
    return [
        ContributionDisposition(item_id=item_id, disposition="accepted") for item_id in item_ids
    ]


def _rejected(*item_ids: str) -> list[ContributionDisposition]:
    return [
        ContributionDisposition(item_id=item_id, disposition="rejected") for item_id in item_ids
    ]


def _contribution(
    parent: ParsedKnowledgeRevision,
    items: list,
    *,
    status: str = "finalized",
    space_id: str | None = None,
) -> KnowledgeContribution:
    return KnowledgeContribution(
        contribution_id="contrib:1",
        space_id=space_id or parent.space_id,
        producer="producer:lab",
        produced_at=NOW,
        status=status,
        items=items,
    )


def _bob_item() -> ProposeEntity:
    return ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob"))


def _reason(exc: GovernedMaterializationIntegrityError) -> str:
    return str(exc.details.get("reason"))


def test_01_happy_path_entity_and_assertion_round_trip() -> None:
    parent = _parent()
    contrib = _contribution(
        parent,
        [
            ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
            ProposeAssertion(
                item_id="i2",
                assertion=_literal("asrt:bob-title", "ent:bob", "Bob"),
            ),
        ],
    )
    result = _call(
        parent=parent,
        contribution=contrib,
        dispositions=_accepted("i1", "i2"),
        publication=_publication(parent),
    )
    command = result.command
    assert isinstance(command, PublishKnowledgeRevisionCommand)
    assert command.parent_revision_id == parent.revision_id
    assert command.expected_parent_revision_id == parent.revision_id
    assert command.parent_revision_id == command.expected_parent_revision_id
    assert command.space_id == parent.space_id
    assert command.graph_schema == NATIVE_VNEXT_GRAPH_SCHEMA
    assert result.graph_payload_sha256 == canonical_sha256(command.graph_payload)
    decoded = decode_native_graph_payload(command.graph_payload)
    child = build_parsed_knowledge_revision(
        revision=KnowledgeRevision(
            space_id=command.space_id,
            revision_id="rev:child",
            parent_revision_id=command.parent_revision_id,
            created_at=command.created_at,
            operation_ids=list(command.operation_ids),
            graph_schema=command.graph_schema,
            graph_payload_sha256=result.graph_payload_sha256,
            domain_contract_ref=command.domain_contract_ref,
            semantic_profile_ref=command.semantic_profile_ref,
        ),
        decoded_content=decoded,
    )
    assert "ent:alice" in child.entities_by_id
    assert "ent:bob" in child.entities_by_id
    assert child.get_assertion("asrt:bob-title") is not None
    assert result.accepted_item_ids == ("i1", "i2")
    assert result.rejected_item_ids == ()


def test_02_rejected_items_do_not_change_child_digest() -> None:
    parent = _parent()
    bob = ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob"))
    title = ProposeAssertion(
        item_id="i2",
        assertion=_literal("asrt:bob-title", "ent:bob", "Bob"),
    )
    ghost = ProposeEntity(item_id="i3", entity=Entity(entity_id="ent:ghost"))
    full = _call(
        parent=parent,
        contribution=_contribution(parent, [bob, title, ghost]),
        dispositions=[*_accepted("i1", "i2"), *_rejected("i3")],
        publication=_publication(parent),
    )
    omitted = _call(
        parent=parent,
        contribution=_contribution(parent, [bob, title]),
        dispositions=_accepted("i1", "i2"),
        publication=_publication(parent),
    )
    assert full.graph_payload_sha256 == omitted.graph_payload_sha256
    assert "ent:ghost" not in [item["entity_id"] for item in full.command.graph_payload["entities"]]
    assert full.rejected_item_ids == ("i3",)


def test_03_incomplete_dispositions_fail_closed() -> None:
    parent = _parent()
    contrib = _contribution(parent, [_bob_item()])
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=[],
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "incomplete_dispositions"


def test_04_extra_dispositions_fail_closed() -> None:
    parent = _parent()
    contrib = _contribution(parent, [_bob_item()])
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=_accepted("i1", "i-extra"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "incomplete_dispositions"


def test_05_unresolved_fails_closed() -> None:
    parent = _parent()
    contrib = _contribution(parent, [_bob_item()])
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=[ContributionDisposition(item_id="i1", disposition="unresolved")],
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "unresolved_dispositions"


def test_06_space_mismatch_fails_closed() -> None:
    parent = _parent()
    contrib = _contribution(
        parent,
        [ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob"))],
        space_id="space:other",
    )
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=_accepted("i1"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "contribution_space_mismatch"


def test_07_non_finalized_contribution_fails_closed() -> None:
    parent = _parent()
    contrib = _contribution(
        parent,
        [ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob"))],
        status="draft",
    )
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=_accepted("i1"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "contribution_not_finalized"


def test_08_expected_parent_mismatch_fails_closed() -> None:
    parent = _parent()
    contrib = _contribution(parent, [_bob_item()])
    publication = GovernedPublicationIdentity(
        operation_ids=("op:child",),
        created_at=NOW,
        expected_parent_revision_id="rev:stale",
    )
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=_accepted("i1"),
            publication=publication,
        )
    assert _reason(exc.value) == "expected_parent_mismatch"


def test_09_duplicate_contribution_item_ids_fail_closed() -> None:
    parent = _parent()
    contrib = KnowledgeContribution.model_construct(
        contribution_id="contrib:1",
        space_id=parent.space_id,
        producer="producer:lab",
        produced_at=NOW,
        status="finalized",
        items=[
            ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
            ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:cara")),
        ],
    )
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=_accepted("i1"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "duplicate_contribution_item_ids"


def test_10_retract_removes_target_and_missing_fails() -> None:
    parent = _parent()
    result = _call(
        parent=parent,
        contribution=_contribution(
            parent,
            [RetractAssertion(item_id="i1", target_assertion_id="asrt:alice-title")],
        ),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    assert all(
        item["assertion_id"] != "asrt:alice-title"
        for item in result.command.graph_payload["assertions"]
    )
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [RetractAssertion(item_id="i1", target_assertion_id="asrt:missing")],
            ),
            dispositions=_accepted("i1"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "retract_missing_target"


def test_11_supersede_replaces_target_and_collision_fails() -> None:
    parent = _parent(
        entities=[Entity(entity_id="ent:alice"), Entity(entity_id="ent:bob")],
        assertions=[
            _literal("asrt:alice-title", "ent:alice", "Alice"),
            _literal("asrt:bob-title", "ent:bob", "Bob"),
        ],
    )
    result = _call(
        parent=parent,
        contribution=_contribution(
            parent,
            [
                SupersedeAssertion(
                    item_id="i1",
                    target_assertion_id="asrt:alice-title",
                    replacement_assertion=_literal("asrt:alice-renamed", "ent:alice", "Alicia"),
                )
            ],
        ),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    ids = {item["assertion_id"] for item in result.command.graph_payload["assertions"]}
    assert "asrt:alice-title" not in ids
    assert "asrt:alice-renamed" in ids
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    SupersedeAssertion(
                        item_id="i1",
                        target_assertion_id="asrt:alice-title",
                        replacement_assertion=_literal("asrt:bob-title", "ent:alice", "stolen"),
                    )
                ],
            ),
            dispositions=_accepted("i1"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "supersede_replacement_collision"


def test_12_assertion_collision_and_idempotent_replay() -> None:
    parent = _parent()
    same = ProposeAssertion(
        item_id="i1",
        assertion=_literal("asrt:alice-title", "ent:alice", "Alice"),
    )
    replay = _call(
        parent=parent,
        contribution=_contribution(parent, [same]),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    assert "asrt:alice-title" in [
        item["assertion_id"] for item in replay.command.graph_payload["assertions"]
    ]
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeAssertion(
                        item_id="i1",
                        assertion=_literal("asrt:alice-title", "ent:alice", "Different"),
                    )
                ],
            ),
            dispositions=_accepted("i1"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "assertion_id_collision"


def test_13_missing_subject_fails_via_structural_validation() -> None:
    parent = _parent()
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeAssertion(
                        item_id="i1",
                        assertion=_literal("asrt:ghost", "ent:missing", "Nope"),
                    )
                ],
            ),
            dispositions=_accepted("i1"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "child_structural_integrity"


def test_14_identity_add_remove_merge_and_reject() -> None:
    parent = _parent(
        entities=[Entity(entity_id="ent:alice"), Entity(entity_id="ent:bob")],
        assertions=[
            _literal("asrt:alice-title", "ent:alice", "Alice"),
            _literal("asrt:bob-title", "ent:bob", "Bob"),
            Assertion(
                assertion_id="asrt:bob-reports",
                subject_entity_id="ent:bob",
                predicate="lab:reports_to",
                value=EntityRefValue(entity_id="ent:alice"),
                metadata=_meta(),
            ),
        ],
        aliases=[
            IdentityAlias(
                alias_id="al:old",
                entity_id="ent:alice",
                alias_text="oldname",
                standing=KnowledgeStanding.ESTABLISHED,
            )
        ],
    )
    added = _call(
        parent=parent,
        contribution=_contribution(
            parent,
            [
                ProposeIdentityDecision(
                    item_id="i1",
                    decision=IdentityDecisionV3(
                        decision_id="iddec:alias",
                        space_id=parent.space_id,
                        decision_kind=IdentityDecisionKind.ALIAS_ADD,
                        subject_entity_ids=["ent:alice"],
                        alias="aka-alice",
                        created_at=NOW,
                    ),
                )
            ],
        ),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    aliases = {item["alias_id"]: item for item in added.command.graph_payload["aliases"]}
    assert aliases["iddec:alias"]["alias_text"] == "aka-alice"

    removed = _call(
        parent=parent,
        contribution=_contribution(
            parent,
            [
                ProposeIdentityDecision(
                    item_id="i1",
                    decision=IdentityDecisionV3(
                        decision_id="iddec:remove",
                        space_id=parent.space_id,
                        decision_kind=IdentityDecisionKind.ALIAS_REMOVE,
                        subject_entity_ids=["ent:alice"],
                        alias="oldname",
                        created_at=NOW,
                    ),
                )
            ],
        ),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    assert all(item["alias_id"] != "al:old" for item in removed.command.graph_payload["aliases"])

    merged = _call(
        parent=parent,
        contribution=_contribution(
            parent,
            [
                ProposeIdentityDecision(
                    item_id="i1",
                    decision=IdentityDecisionV3(
                        decision_id="iddec:merge",
                        space_id=parent.space_id,
                        decision_kind=IdentityDecisionKind.MERGE,
                        subject_entity_ids=["ent:alice", "ent:bob"],
                        target_entity_ids=["ent:alice"],
                        created_at=NOW,
                    ),
                )
            ],
        ),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    entity_ids = {item["entity_id"] for item in merged.command.graph_payload["entities"]}
    assert entity_ids == {"ent:alice"}
    bob_title = next(
        item
        for item in merged.command.graph_payload["assertions"]
        if item["assertion_id"] == "asrt:bob-title"
    )
    assert bob_title["subject_entity_id"] == "ent:alice"

    rejected = _call(
        parent=parent,
        contribution=_contribution(
            parent,
            [
                ProposeIdentityDecision(
                    item_id="i1",
                    decision=IdentityDecisionV3(
                        decision_id="iddec:reject",
                        space_id=parent.space_id,
                        decision_kind=IdentityDecisionKind.REJECT_CANDIDATE,
                        subject_entity_ids=["ent:candidate"],
                        created_at=NOW,
                    ),
                )
            ],
        ),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    assert {item["entity_id"] for item in rejected.command.graph_payload["entities"]} == {
        "ent:alice",
        "ent:bob",
    }


def test_15_non_materializable_identity_kinds_fail_closed() -> None:
    parent = _parent()
    for kind, kwargs in (
        (
            IdentityDecisionKind.SPLIT,
            {"subject_entity_ids": ["ent:alice"], "target_entity_ids": ["ent:a", "ent:b"]},
        ),
        (
            IdentityDecisionKind.UNMERGE,
            {"subject_entity_ids": ["ent:alice"], "target_entity_ids": ["ent:a"]},
        ),
        (IdentityDecisionKind.MARK_AMBIGUOUS, {"subject_entity_ids": ["ent:alice"]}),
        (IdentityDecisionKind.HUMAN_OVERRIDE, {"subject_entity_ids": ["ent:alice"]}),
    ):
        with pytest.raises(GovernedMaterializationIntegrityError) as exc:
            _call(
                parent=parent,
                contribution=_contribution(
                    parent,
                    [
                        ProposeIdentityDecision(
                            item_id="i1",
                            decision=IdentityDecisionV3(
                                decision_id=f"iddec:{kind.value}",
                                space_id=parent.space_id,
                                decision_kind=kind,
                                created_at=NOW,
                                **kwargs,
                            ),
                        )
                    ],
                ),
                dispositions=_accepted("i1"),
                publication=_publication(parent),
            )
        assert _reason(exc.value) == "identity_kind_not_materializable_in_v5_1"


def test_16_disposition_list_order_does_not_change_digest() -> None:
    parent = _parent()
    items = [
        ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
        ProposeAssertion(
            item_id="i2",
            assertion=_literal("asrt:bob-title", "ent:bob", "Bob"),
        ),
    ]
    contrib = _contribution(parent, items)
    first = _call(
        parent=parent,
        contribution=contrib,
        dispositions=_accepted("i1", "i2"),
        publication=_publication(parent),
    )
    second = _call(
        parent=parent,
        contribution=contrib,
        dispositions=list(reversed(_accepted("i1", "i2"))),
        publication=_publication(parent),
    )
    assert first.graph_payload_sha256 == second.graph_payload_sha256


def test_17_parent_revision_is_unchanged() -> None:
    parent = _parent()
    before_entities = set(parent.entities_by_id)
    before_assertions = set(parent.assertions_by_id)
    _call(
        parent=parent,
        contribution=_contribution(
            parent, [ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob"))]
        ),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    assert set(parent.entities_by_id) == before_entities
    assert set(parent.assertions_by_id) == before_assertions


def test_18_command_parent_fields_are_equal() -> None:
    parent = _parent()
    result = _call(
        parent=parent,
        contribution=_contribution(
            parent, [ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob"))]
        ),
        dispositions=_accepted("i1"),
        publication=_publication(parent),
    )
    first = result.command
    assert first.parent_revision_id == first.expected_parent_revision_id
    snapshot = result.graph_payload
    first.graph_payload["entities"] = []
    first.operation_ids.append("op:mutated")
    second = result.command
    assert second.graph_payload == snapshot
    assert second.operation_ids == ["op:child"]
    assert result.graph_payload == snapshot
    assert result.graph_payload_sha256 == canonical_sha256(snapshot)
    assert result.graph_payload_sha256 == canonical_sha256(second.graph_payload)


def test_19_org_and_buddy_fixtures_share_the_engine() -> None:
    org_context, _ = _build_from_fixture(
        "organizational_memory_v1.json",
        domain_contract=_org_domain_contract(),
        semantic_profile=_org_semantic_profile(),
        contract_digest=ORG_CONTRACT_DIGEST,
        profile_digest=ORG_PROFILE_DIGEST,
    )
    org_parent = org_context.parsed
    org_title = next(
        Assertion.model_validate(item)
        for item in json.loads(
            (FIXTURES_DIR / "organizational_memory_v1.json").read_text(encoding="utf-8")
        )["assertions"]
        if item["predicate"] == "organization:title"
    )
    org_result = _call(
        parent=org_parent,
        contribution=_contribution(
            org_parent,
            [
                ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:new-org")),
                ProposeAssertion(
                    item_id="i2",
                    assertion=org_title.model_copy(
                        update={
                            "assertion_id": "asrt:new-org-title",
                            "subject_entity_id": "ent:new-org",
                            "value": LiteralValue(value={"title": "New desk"}),
                        }
                    ),
                ),
            ],
        ),
        dispositions=_accepted("i1", "i2"),
        publication=_publication(org_parent),
        domain_contract=_org_domain_contract(),
        semantic_profile=_org_semantic_profile(),
    )
    entity_ids = [item["entity_id"] for item in org_result.command.graph_payload["entities"]]
    assert "ent:new-org" in entity_ids
    decoded = decode_native_graph_payload(org_result.command.graph_payload)
    assert any(item.assertion_id == "asrt:new-org-title" for item in decoded.assertions)

    buddy_context, _ = _buddy_context(_buddy_request())
    buddy_parent = buddy_context.parsed
    buddy_result = _call(
        parent=buddy_parent,
        contribution=_contribution(
            buddy_parent,
            [ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:new-buddy"))],
        ),
        dispositions=_accepted("i1"),
        publication=_publication(buddy_parent),
        domain_contract=_buddy_domain_contract(),
        semantic_profile=_buddy_semantic_profile(),
    )
    assert "ent:new-buddy" in [
        item["entity_id"] for item in buddy_result.command.graph_payload["entities"]
    ]
    source = MATERIALIZATION_SRC.read_text(encoding="utf-8")
    for banned in ('"GM"', "'GM'", "PLAYER", "campaign_id", "world_id", "dungeonbuddy"):
        assert banned not in source


def test_20_source_has_no_world_review_transport() -> None:
    source = MATERIALIZATION_SRC.read_text(encoding="utf-8")
    for banned in (
        "world_id",
        "campaign_id",
        "review_materialization",
        "ContributionReview",
        "dungeonmind_dnd",
        '"GM"',
        "PLAYER",
    ):
        assert banned not in source


def test_21_public_export_is_materializer_not_publisher() -> None:
    exported = (VNEXT_SRC / "__init__.py").read_text(encoding="utf-8")
    assert "materialize_governed_revision" in exported
    assert "GovernedMaterializationResult" in exported
    assert "publish_knowledge_revision(" not in exported
    assert "KnowledgeHead" not in MATERIALIZATION_SRC.read_text(encoding="utf-8")


def test_22_runtime_does_not_claim_acceptance() -> None:
    source = MATERIALIZATION_SRC.read_text(encoding="utf-8")
    assert "V5_1_GENERIC_GOVERNED_MATERIALIZATION_ACCEPTED" not in source


def test_23_materialization_10k_benchmark_records_shape() -> None:
    path = REPO_ROOT / "Docs" / "Benchmarks" / "vnext_governed_materialization_10k_v1.json"
    if not path.is_file():
        pytest.skip("governed-materialization 10k artifact not yet pinned")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["characterization_only"] is True
    assert payload["exact_base"] == IMPLEMENTATION_BASE
    run = payload["runs"]["tiny_accepted_change_10k"]
    assert run["parent_entity_count"] == 10000
    assert run["accepted_item_count"] == 1
    assert run["bytes_written"] == 0
    assert "p95_ms" in run
    assert "validate_p50_ms" in run
    assert "validate_p95_ms" in run
    assert "serialize_hash_p50_ms" in run
    assert "serialize_hash_p95_ms" in run


def test_24_frozen_v0_aggregate_unchanged() -> None:
    digest_path = Path(__file__).resolve().parents[1] / "fixtures" / "vnext" / "CONTRACT_DIGEST.txt"
    if digest_path.is_file():
        assert digest_path.read_text(encoding="utf-8").strip() == CANONICAL_V0_AGGREGATE
    assert (
        CANONICAL_V0_AGGREGATE == "fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea"
    )


def test_25_non_native_parent_fails_closed() -> None:
    parent = _parent(graph_schema="dm_union_graph_v6")
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent, [ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob"))]
            ),
            dispositions=_accepted("i1"),
            publication=_publication(parent),
        )
    assert _reason(exc.value) == "parent_not_native_vnext"


def test_26_undeclared_predicate_fails_closed() -> None:
    parent = _parent()
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
                    ProposeAssertion(
                        item_id="i2",
                        assertion=Assertion(
                            assertion_id="asrt:bob-unknown",
                            subject_entity_id="ent:bob",
                            predicate="lab:unknown",
                            value=LiteralValue(value="x"),
                            metadata=_meta(),
                        ),
                    ),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )
    assert _reason(exc.value) == "undeclared_semantic_profile"

    with pytest.raises(GovernedMaterializationIntegrityError) as kind_exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
                    ProposeAssertion(
                        item_id="i2",
                        assertion=_literal("asrt:bob-title", "ent:bob", "Bob").model_copy(
                            update={"value": EntityRefValue(entity_id="ent:alice")}
                        ),
                    ),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )
    assert _reason(kind_exc.value) == "undeclared_semantic_profile"


def test_27_undeclared_domain_vocabulary_fails_closed() -> None:
    parent = _parent()
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
                    ProposeAssertion(
                        item_id="i2",
                        assertion=_literal("asrt:bob-title", "ent:bob", "Bob").model_copy(
                            update={
                                "metadata": AssertionMetadata(
                                    scope=[ScopeBinding(axis="lab:other", value="one")],
                                    visibility=PublicVisibility(),
                                    epistemic_basis=EpistemicBasis.ASSERTED,
                                    claim_mode="lab:fact",
                                    standing=KnowledgeStanding.ESTABLISHED,
                                    evidence_ref_ids=["ev:lab"],
                                    temporal_scope=TimelessTemporalScope(),
                                )
                            }
                        ),
                    ),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )
    assert _reason(exc.value) == "undeclared_domain_vocabulary"

    with pytest.raises(GovernedMaterializationIntegrityError) as claim_exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
                    ProposeAssertion(
                        item_id="i2",
                        assertion=_literal("asrt:bob-title", "ent:bob", "Bob").model_copy(
                            update={
                                "metadata": AssertionMetadata(
                                    scope=[ScopeBinding(axis="lab:scope", value="one")],
                                    visibility=PublicVisibility(),
                                    epistemic_basis=EpistemicBasis.ASSERTED,
                                    claim_mode="lab:belief",
                                    standing=KnowledgeStanding.ESTABLISHED,
                                    evidence_ref_ids=["ev:lab"],
                                    temporal_scope=TimelessTemporalScope(),
                                )
                            }
                        ),
                    ),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )
    assert _reason(claim_exc.value) == "undeclared_domain_vocabulary"

    with pytest.raises(GovernedMaterializationIntegrityError) as vis_exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
                    ProposeAssertion(
                        item_id="i2",
                        assertion=_literal("asrt:bob-title", "ent:bob", "Bob").model_copy(
                            update={
                                "metadata": AssertionMetadata(
                                    scope=[ScopeBinding(axis="lab:scope", value="one")],
                                    visibility=LabelsAnyVisibility(labels=["lab:secret"]),
                                    epistemic_basis=EpistemicBasis.ASSERTED,
                                    claim_mode="lab:fact",
                                    standing=KnowledgeStanding.ESTABLISHED,
                                    evidence_ref_ids=["ev:lab"],
                                    temporal_scope=TimelessTemporalScope(),
                                )
                            }
                        ),
                    ),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )
    assert _reason(vis_exc.value) == "undeclared_domain_vocabulary"

    with pytest.raises(GovernedMaterializationIntegrityError) as temporal_exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
                    ProposeAssertion(
                        item_id="i2",
                        assertion=_literal("asrt:bob-title", "ent:bob", "Bob").model_copy(
                            update={
                                "metadata": AssertionMetadata(
                                    scope=[ScopeBinding(axis="lab:scope", value="one")],
                                    visibility=PublicVisibility(),
                                    epistemic_basis=EpistemicBasis.ASSERTED,
                                    claim_mode="lab:fact",
                                    standing=KnowledgeStanding.ESTABLISHED,
                                    evidence_ref_ids=["ev:lab"],
                                    temporal_scope=DomainTemporalScope(
                                        schema="lab:calendar",
                                        payload={"era": "1"},
                                    ),
                                )
                            }
                        ),
                    ),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )
    assert _reason(temporal_exc.value) == "undeclared_domain_vocabulary"

    with pytest.raises(GovernedMaterializationIntegrityError) as metadata_exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
                    ProposeAssertion(
                        item_id="i2",
                        assertion=_literal("asrt:bob-title", "ent:bob", "Bob").model_copy(
                            update={
                                "metadata": AssertionMetadata(
                                    scope=[ScopeBinding(axis="lab:scope", value="one")],
                                    visibility=PublicVisibility(),
                                    epistemic_basis=EpistemicBasis.ASSERTED,
                                    claim_mode="lab:fact",
                                    standing=KnowledgeStanding.ESTABLISHED,
                                    evidence_ref_ids=["ev:lab"],
                                    temporal_scope=TimelessTemporalScope(),
                                    domain_metadata=[
                                        DomainMetadataEntry(
                                            schema="lab:note",
                                            payload={"n": 1},
                                        )
                                    ],
                                )
                            }
                        ),
                    ),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )
    assert _reason(metadata_exc.value) == "undeclared_domain_vocabulary"


def test_28_descriptor_pin_mismatch_fails_closed() -> None:
    parent = _parent()
    contract, profile = _lab_descriptors()
    contrib = _contribution(
        parent, [ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob"))]
    )
    with pytest.raises(GovernedMaterializationIntegrityError) as identity_exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=_accepted("i1"),
            domain_contract=contract.model_copy(update={"domain_id": "lab.other"}),
            semantic_profile=profile,
        )
    assert _reason(identity_exc.value) == "domain_contract_identity_mismatch"

    with pytest.raises(GovernedMaterializationIntegrityError) as digest_exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=_accepted("i1"),
            domain_contract=contract.model_copy(update={"admission_policy_id": "lab.other"}),
            semantic_profile=profile,
        )
    assert _reason(digest_exc.value) == "domain_contract_digest_mismatch"

    with pytest.raises(GovernedMaterializationIntegrityError) as profile_exc:
        _call(
            parent=parent,
            contribution=contrib,
            dispositions=_accepted("i1"),
            domain_contract=contract,
            semantic_profile=profile.model_copy(update={"profile_id": "lab.other"}),
        )
    assert _reason(profile_exc.value) == "semantic_profile_identity_mismatch"


def test_29_identity_decision_ids_close_against_accepted_decisions() -> None:
    parent = _parent()
    identity = ProposeIdentityDecision(
        item_id="i1",
        decision=IdentityDecisionV3(
            decision_id="iddec:alias",
            space_id=parent.space_id,
            decision_kind=IdentityDecisionKind.ALIAS_ADD,
            subject_entity_ids=["ent:alice"],
            alias="aka-alice",
            created_at=NOW,
        ),
    )
    entity = ProposeEntity(item_id="i2", entity=Entity(entity_id="ent:bob"))
    closed = _call(
        parent=parent,
        contribution=_contribution(parent, [identity, entity]),
        dispositions=[
            ContributionDisposition(
                item_id="i1",
                disposition="accepted",
                identity_decision_ids=["iddec:alias"],
            ),
            ContributionDisposition(
                item_id="i2",
                disposition="accepted",
                identity_decision_ids=["iddec:alias"],
            ),
        ],
    )
    aliases = {item["alias_id"]: item for item in closed.command.graph_payload["aliases"]}
    assert aliases["iddec:alias"]["alias_text"] == "aka-alice"

    with pytest.raises(GovernedMaterializationIntegrityError) as missing_exc:
        _call(
            parent=parent,
            contribution=_contribution(parent, [identity, entity]),
            dispositions=[
                ContributionDisposition(item_id="i1", disposition="accepted"),
                ContributionDisposition(
                    item_id="i2",
                    disposition="accepted",
                    identity_decision_ids=["iddec:missing"],
                ),
            ],
        )
    assert _reason(missing_exc.value) == "identity_decision_id_unresolved"

    with pytest.raises(GovernedMaterializationIntegrityError) as rejected_exc:
        _call(
            parent=parent,
            contribution=_contribution(parent, [identity, entity]),
            dispositions=[
                ContributionDisposition(item_id="i1", disposition="rejected"),
                ContributionDisposition(
                    item_id="i2",
                    disposition="accepted",
                    identity_decision_ids=["iddec:alias"],
                ),
            ],
        )
    assert _reason(rejected_exc.value) == "identity_decision_id_unresolved"


def test_30_duplicate_identity_decision_id_fails_closed() -> None:
    parent = _parent(
        entities=[Entity(entity_id="ent:alice"), Entity(entity_id="ent:bob")],
        assertions=[
            _literal("asrt:alice-title", "ent:alice", "Alice"),
            _literal("asrt:bob-title", "ent:bob", "Bob"),
        ],
    )
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeIdentityDecision(
                        item_id="i1",
                        decision=IdentityDecisionV3(
                            decision_id="iddec:shared",
                            space_id=parent.space_id,
                            decision_kind=IdentityDecisionKind.REJECT_CANDIDATE,
                            subject_entity_ids=["ent:alice"],
                            created_at=NOW,
                        ),
                    ),
                    ProposeIdentityDecision(
                        item_id="i2",
                        decision=IdentityDecisionV3(
                            decision_id="iddec:shared",
                            space_id=parent.space_id,
                            decision_kind=IdentityDecisionKind.MERGE,
                            subject_entity_ids=["ent:alice", "ent:bob"],
                            target_entity_ids=["ent:alice"],
                            created_at=NOW,
                        ),
                    ),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )
    assert _reason(exc.value) == "duplicate_identity_decision_id"


def test_31_non_active_identity_decision_fails_closed() -> None:
    parent = _parent()
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeIdentityDecision(
                        item_id="i1",
                        decision=IdentityDecisionV3(
                            decision_id="iddec:alias",
                            space_id=parent.space_id,
                            decision_kind=IdentityDecisionKind.ALIAS_ADD,
                            subject_entity_ids=["ent:alice"],
                            alias="aka-alice",
                            status=IdentityDecisionStatus.RETRACTED,
                            created_at=NOW,
                        ),
                    )
                ],
            ),
            dispositions=_accepted("i1"),
        )
    assert _reason(exc.value) == "identity_decision_not_active"


def test_32_identity_supersession_fails_closed() -> None:
    parent = _parent()
    with pytest.raises(GovernedMaterializationIntegrityError) as exc:
        _call(
            parent=parent,
            contribution=_contribution(
                parent,
                [
                    ProposeIdentityDecision(
                        item_id="i1",
                        decision=IdentityDecisionV3(
                            decision_id="iddec:alias",
                            space_id=parent.space_id,
                            decision_kind=IdentityDecisionKind.ALIAS_ADD,
                            subject_entity_ids=["ent:alice"],
                            alias="aka-alice",
                            supersedes_decision_ids=["iddec:old"],
                            created_at=NOW,
                        ),
                    )
                ],
            ),
            dispositions=_accepted("i1"),
        )
    assert _reason(exc.value) == "identity_supersession_not_materializable_in_v5_1"


def test_v3_authored_predicate_namespace_publishes_without_opening_other_terms() -> None:
    profile = SemanticProfileDescriptorV3(
        profile_id="lab.profile",
        profile_revision="2",
        term_namespaces=["lab", "lab.custom"],
        predicates=[SemanticProfilePredicate(term="lab:title", allowed_value_kinds=["literal"])],
        open_predicate_namespaces=[
            OpenPredicateNamespace(namespace="lab.custom", allowed_value_kinds=["entity_ref"])
        ],
    )
    parent = _parent(profile=profile)

    def relationship(predicate: str, value: EntityRefValue | LiteralValue) -> Assertion:
        return Assertion(
            assertion_id="asrt:custom",
            subject_entity_id="ent:alice",
            predicate=predicate,
            value=value,
            metadata=_meta(),
        )

    def publish(assertion: Assertion):
        return _call(
            parent=parent,
            semantic_profile=profile,
            contribution=_contribution(
                parent,
                [
                    ProposeEntity(item_id="i1", entity=Entity(entity_id="ent:bob")),
                    ProposeAssertion(item_id="i2", assertion=assertion),
                ],
            ),
            dispositions=_accepted("i1", "i2"),
        )

    result = publish(relationship("lab.custom:works_at", EntityRefValue(entity_id="ent:bob")))
    assert result.command.semantic_profile_ref.profile_revision == "2"
    assert any(
        item["predicate"] == "lab.custom:works_at"
        for item in result.command.graph_payload["assertions"]
    )

    for rejected in (
        relationship("lab.custom:works_at", LiteralValue(value="Bob")),
        relationship("lab:works_at", EntityRefValue(entity_id="ent:bob")),
    ):
        with pytest.raises(GovernedMaterializationIntegrityError) as exc:
            publish(rejected)
        assert _reason(exc.value) == "undeclared_semantic_profile"
