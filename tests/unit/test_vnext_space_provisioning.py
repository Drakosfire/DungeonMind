"""Acceptance witnesses for MIND-minted atomic empty-space provisioning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dungeonmind.application.vnext import (
    KnowledgeSpaceProvisioningConflictError,
    create_empty_space,
    initialize_empty_knowledge_space,
)
from dungeonmind.application.vnext.errors import KnowledgePublicationIntegrityError
from dungeonmind.contracts.vnext.domain import (
    DomainContractDescriptor,
    SemanticProfileDescriptorV2,
)
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory.vnext_knowledge import (
    InMemoryKnowledgeRevisionRepository,
)

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _domain() -> DomainContractDescriptor:
    return DomainContractDescriptor(
        domain_id="test.space-provisioning",
        domain_revision="1",
        admission_policy_id="test.space-provisioning.always",
    )


def _profile(revision: str = "1") -> SemanticProfileDescriptorV2:
    return SemanticProfileDescriptorV2(
        profile_id="test.space-provisioning.profile",
        profile_revision=revision,
        term_namespaces=["test"],
    )


def _create(repo, allocation_id: str, *, profile=None, created_at=NOW):
    return create_empty_space(
        repository=repo,
        allocation_id=allocation_id,
        created_at=created_at,
        domain_contract=_domain(),
        semantic_profile=profile or _profile(),
    )


def test_same_key_replays_same_minted_space_and_empty_genesis(monkeypatch) -> None:
    ids = iter(["space:dm:minted-1", "space:dm:unused-retry"])
    monkeypatch.setattr(
        "dungeonmind.application.vnext.space_provisioning._new_space_id",
        lambda: next(ids),
    )
    repo = InMemoryKnowledgeRevisionRepository()

    first = _create(repo, "allocation:stable")
    retry = _create(repo, "allocation:stable", created_at=NOW + timedelta(seconds=2))

    assert first == retry
    assert first.space_id == "space:dm:minted-1"
    assert first.publication_receipt.expected_parent_revision_id is None
    stored = repo.get_revision(first.space_id, first.publication_receipt.published_revision_id)
    assert stored is not None
    assert stored.graph_payload == {
        "entities": [],
        "assertions": [],
        "aliases": [],
        "evidence": [],
    }
    head = repo.get_head(first.space_id)
    assert head is not None
    assert head.head_revision_id == first.publication_receipt.published_revision_id
    assert len(repo.head_events(first.space_id)) == 1
    assert len(repo._space_provisioning) == 1
    assert len(repo._receipts) == 1


def test_same_key_with_changed_semantics_conflicts_without_mutation() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    first = _create(repo, "allocation:conflict")

    with pytest.raises(KnowledgeSpaceProvisioningConflictError):
        _create(repo, "allocation:conflict", profile=_profile("2"))

    assert repo.get_space_provisioning_receipt("allocation:conflict") == first
    head = repo.get_head(first.space_id)
    assert head is not None
    assert head.head_revision_id == first.publication_receipt.published_revision_id
    assert len(repo.head_events(first.space_id)) == 1
    assert len(repo._space_provisioning) == 1


def test_distinct_keys_mint_isolated_space_ids() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    one = _create(repo, "allocation:one")
    two = _create(repo, "allocation:two")

    assert one.space_id != two.space_id
    assert (
        one.publication_receipt.published_revision_id
        != two.publication_receipt.published_revision_id
    )
    assert repo.get_head(one.space_id) is not None
    assert repo.get_head(two.space_id) is not None
    assert len(repo._space_provisioning) == 2


def test_existing_space_id_collision_mints_another_id_without_aliasing(monkeypatch) -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    existing = initialize_empty_knowledge_space(
        repository=repo,
        space_id="space:dm:occupied",
        initialization_id="init:occupied",
        created_at=NOW,
        domain_contract=_domain(),
        semantic_profile=_profile(),
    )
    candidates = iter(["space:dm:occupied", "space:dm:fresh"])
    monkeypatch.setattr(
        "dungeonmind.application.vnext.space_provisioning._new_space_id",
        lambda: next(candidates),
    )

    provisioned = _create(repo, "allocation:after-collision")

    assert provisioned.space_id == "space:dm:fresh"
    assert repo.get_publication_receipt("space:dm:occupied", "init:occupied") == existing
    assert repo.get_space_provisioning_receipt("allocation:after-collision") == provisioned


def test_failure_before_commit_leaves_no_allocation_or_genesis(monkeypatch) -> None:
    def fail_after_revision_insert() -> None:
        raise RuntimeError("injected provisioning rollback")

    repo = InMemoryKnowledgeRevisionRepository(
        after_revision_insert=fail_after_revision_insert
    )
    monkeypatch.setattr(
        "dungeonmind.application.vnext.space_provisioning._new_space_id",
        lambda: "space:dm:rollback",
    )

    with pytest.raises(RuntimeError, match="injected provisioning rollback"):
        _create(repo, "allocation:rollback")

    assert repo._space_provisioning == {}
    assert repo._receipts == {}
    assert repo._revisions == {}
    assert repo._heads == {}
    assert repo._events == []
    assert repo.get_head("space:dm:rollback") is None


def test_post_commit_response_loss_retry_recovers_original_receipt(monkeypatch) -> None:
    calls = 0

    def lose_response_once() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated response loss after commit")

    ids = iter(["space:dm:committed", "space:dm:should-not-commit"])
    monkeypatch.setattr(
        "dungeonmind.application.vnext.space_provisioning._new_space_id",
        lambda: next(ids),
    )
    repo = InMemoryKnowledgeRevisionRepository(
        after_space_provisioning_commit=lose_response_once
    )

    with pytest.raises(RuntimeError, match="response loss"):
        _create(repo, "allocation:response-loss")
    recovered = _create(repo, "allocation:response-loss")

    assert recovered.space_id == "space:dm:committed"
    assert repo.get_space_provisioning_receipt("allocation:response-loss") == recovered
    assert len(repo._space_provisioning) == 1
    assert len(repo.head_events(recovered.space_id)) == 1


def test_invalid_allocation_key_fails_before_mutation() -> None:
    repo = InMemoryKnowledgeRevisionRepository()
    with pytest.raises(KnowledgePublicationIntegrityError) as caught:
        _create(repo, " ")
    assert caught.value.reason == "allocation_id_blank"
    assert repo._space_provisioning == {}
    assert repo._heads == {}


def test_repository_recomputes_request_digest_before_any_mutation() -> None:
    repo = InMemoryKnowledgeRevisionRepository()

    class ForgedRequestDigestRepository:
        def provision_empty_space(self, command, **kwargs):
            return repo.provision_empty_space(
                command,
                allocation_id=kwargs["allocation_id"],
                request_sha256="0" * 64,
                publication_id=kwargs["publication_id"],
            )

    with pytest.raises(PersistenceIntegrityError, match="request digest mismatch"):
        _create(ForgedRequestDigestRepository(), "allocation:forged-request")

    assert repo._space_provisioning == {}
    assert repo._receipts == {}
    assert repo._revisions == {}
    assert repo._heads == {}
    assert repo._events == []
