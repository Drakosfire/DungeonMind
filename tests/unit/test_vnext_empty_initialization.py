"""Acceptance witnesses for public empty native KnowledgeSpace initialization."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dungeonmind.application.vnext import initialize_empty_knowledge_space
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationIntegrityError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
)
from dungeonmind.application.vnext.materialization import (
    GovernedPublicationIdentity,
    decode_native_graph_payload,
    materialize_governed_revision,
)
from dungeonmind.application.vnext.publication import publish_governed_materialization
from dungeonmind.contracts.vnext.contribution import (
    ContributionDisposition,
    KnowledgeContribution,
    ProposeEntity,
)
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    Entity,
    OpenPredicateNamespace,
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.infrastructure.memory.vnext_knowledge import InMemoryKnowledgeRevisionRepository

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _domain() -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.empty",
        domain_revision="1",
        admission_policy_id="test.empty.always",
    )


def _profile_v2() -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.empty.profile",
        profile_revision="2",
        term_namespaces=["test"],
    )


def _profile_v3() -> SemanticProfileDescriptorV3:
    return SemanticProfileDescriptorV3(
        profile_id="test.empty.profile",
        profile_revision="3",
        term_namespaces=["test"],
        open_predicate_namespaces=[
            OpenPredicateNamespace(namespace="test", allowed_value_kinds=["literal"])
        ],
    )


def _initialize(
    repo: InMemoryKnowledgeRevisionRepository,
    *,
    space_id: str = "space:empty",
    initialization_id: str = "init:empty",
    created_at: datetime = NOW,
    domain: DomainContractDescriptor | None = None,
    profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3 | None = None,
):
    return initialize_empty_knowledge_space(
        repository=repo,
        space_id=space_id,
        initialization_id=initialization_id,
        created_at=created_at,
        domain_contract=domain or _domain(),
        semantic_profile=profile or _profile_v2(),
    )


@pytest.mark.parametrize("profile", [_profile_v2(), _profile_v3()])
def test_public_initializer_publishes_exact_empty_native_genesis(profile) -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    domain = _domain()
    receipt = _initialize(repo, domain=domain, profile=profile)

    head = repo.get_head("space:empty")
    assert head is not None and head.head_revision_id == receipt.published_revision_id
    stored = repo.get_revision("space:empty", receipt.published_revision_id)
    assert stored is not None
    assert stored.graph_payload == {
        "entities": [],
        "assertions": [],
        "aliases": [],
        "evidence": [],
    }
    revision = stored.revision
    assert revision.parent_revision_id is None
    assert revision.migration_origin_ref is None
    assert revision.operation_ids == ["init:empty"]
    assert revision.domain_contract_ref.descriptor_sha256 == canonical_sha256(
        domain.model_dump(mode="json")
    )
    assert revision.semantic_profile_ref.descriptor_sha256 == canonical_sha256(
        profile.model_dump(mode="json")
    )
    assert len(repo.head_events("space:empty")) == 1


def test_exact_retry_replays_without_new_event_and_changed_intent_conflicts() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    first = _initialize(repo)
    second = _initialize(repo)
    assert second == first
    assert len(repo.head_events("space:empty")) == 1

    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        _initialize(
            repo,
            profile=SemanticProfileDescriptorV2(
                profile_id="test.empty.profile",
                profile_revision="changed",
                term_namespaces=["test"],
            ),
        )
    assert repo.get_head("space:empty").head_revision_id == first.published_revision_id  # type: ignore[union-attr]
    assert len(repo.head_events("space:empty")) == 1


def test_different_initialization_cannot_replace_existing_root() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    first = _initialize(repo)
    with pytest.raises(KnowledgeStaleParentRevisionError):
        _initialize(repo, initialization_id="init:other")
    assert repo.get_head("space:empty").head_revision_id == first.published_revision_id  # type: ignore[union-attr]
    assert len(repo.head_events("space:empty")) == 1


def test_descriptors_are_snapshotted_before_publication() -> None:
    domain = _domain()
    profile = _profile_v2()
    repo = InMemoryKnowledgeRevisionRepository()
    receipt = _initialize(repo, domain=domain, profile=profile)
    stored = repo.get_revision("space:empty", receipt.published_revision_id)
    assert stored is not None
    expected_domain_digest = stored.revision.domain_contract_ref.descriptor_sha256
    expected_profile_digest = stored.revision.semantic_profile_ref.descriptor_sha256

    domain.scope_axes.append("test:later")
    profile.term_namespaces.append("later")
    stored_again = repo.get_revision("space:empty", receipt.published_revision_id)
    assert stored_again is not None
    assert stored_again.revision.domain_contract_ref.descriptor_sha256 == expected_domain_digest
    assert stored_again.revision.semantic_profile_ref.descriptor_sha256 == expected_profile_digest


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"space_id": " "}, "space_id_blank"),
        ({"initialization_id": ""}, "initialization_id_blank"),
        ({"created_at": datetime(2026, 9, 28, 12, 0)}, "created_at_not_timezone_aware"),
    ],
)
def test_invalid_identity_and_time_fail_before_writes(overrides, reason) -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    with pytest.raises(KnowledgePublicationIntegrityError) as caught:
        _initialize(repo, **overrides)
    assert caught.value.reason == reason
    assert repo.get_head("space:empty") is None
    assert repo.head_events("space:empty") == ()


def test_transaction_failure_rolls_back_all_initialization_authority() -> None:
    def fail_after_revision() -> None:
        raise RuntimeError("injected rollback")

    repo = InMemoryKnowledgeRevisionRepository(after_revision_insert=fail_after_revision)
    with pytest.raises(KnowledgePublicationOutcomeUnknownError) as caught:
        _initialize(repo)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert repo.get_head("space:empty") is None
    assert repo.head_events("space:empty") == ()
    assert repo.get_publication_receipt("space:empty", "init:empty") is None


def test_lost_response_recovers_exact_receipt() -> None:
    lost = True

    def lose_once() -> None:
        nonlocal lost
        if lost:
            lost = False
            raise RuntimeError("response lost")

    repo = InMemoryKnowledgeRevisionRepository(after_publication_commit=lose_once)
    receipt = _initialize(repo)
    assert repo.get_publication_receipt("space:empty", "init:empty") == receipt
    assert len(repo.head_events("space:empty")) == 1


def test_two_spaces_share_repository_without_authority_collision() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    one = _initialize(repo, space_id="space:one", initialization_id="init:one")
    two = _initialize(repo, space_id="space:two", initialization_id="init:two")
    assert one.published_revision_id != two.published_revision_id
    assert repo.get_head("space:one").head_revision_id == one.published_revision_id  # type: ignore[union-attr]
    assert repo.get_head("space:two").head_revision_id == two.published_revision_id  # type: ignore[union-attr]


def test_initialization_replay_after_governed_descendant_does_not_rewind_head() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    original = _initialize(repo)
    stored = repo.get_revision("space:empty", original.published_revision_id)
    assert stored is not None
    parent = build_parsed_knowledge_revision(
        revision=stored.revision,
        decoded_content=decode_native_graph_payload(stored.graph_payload),
    )
    materialization = materialize_governed_revision(
        parent=parent,
        contribution=KnowledgeContribution(
            contribution_id="contrib:no-op",
            space_id="space:empty",
            producer="test:initializer",
            produced_at=NOW,
            status="finalized",
            items=[
                ProposeEntity(
                    item_id="item:descendant",
                    entity=Entity(entity_id="entity:descendant"),
                )
            ],
        ),
        dispositions=[
            ContributionDisposition(item_id="item:descendant", disposition="accepted")
        ],
        publication=GovernedPublicationIdentity(
            operation_ids=("op:descendant",),
            created_at=datetime(2026, 9, 28, 13, 0, tzinfo=UTC),
            expected_parent_revision_id=original.published_revision_id,
        ),
        domain_contract=_domain(),
        semantic_profile=_profile_v2(),
    )
    descendant = publish_governed_materialization(
        materialization,
        repository=repo,
        publication_id="publication:descendant",
    )

    replayed = _initialize(repo)
    assert replayed == original
    assert repo.get_head("space:empty").head_revision_id == descendant.published_revision_id  # type: ignore[union-attr]
    assert len(repo.head_events("space:empty")) == 2
