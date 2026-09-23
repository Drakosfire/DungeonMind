"""Acceptance matrix for V5.4 prospective-reference publication."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from pydantic import ValidationError

from dungeonmind.application.vnext.errors import (
    GovernedMaterializationIntegrityError,
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationOutcomeUnknownError,
    ProspectivePublicationIntegrityError,
)
from dungeonmind.application.vnext.materialization import GovernedPublicationIdentity
from dungeonmind.application.vnext.prospective import (
    allocate_prospective_result_id,
    get_prospective_publication,
    publish_prospective_contribution,
    resolve_prospective_contribution,
)
from dungeonmind.contracts.vnext.contribution import ContributionDisposition
from dungeonmind.contracts.vnext.domain import LiteralValue
from dungeonmind.contracts.vnext.prospective import (
    DurableEntityRef,
    KnowledgeProspectivePublication,
    KnowledgeProspectivePublicationResult,
    ProspectiveCreateAssertion,
    ProspectiveCreateEntity,
    ProspectiveEntityRef,
    ProspectiveEntityRefValue,
    ProspectiveKnowledgeContribution,
    ProspectiveResultBinding,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory.vnext_knowledge import InMemoryKnowledgeRevisionRepository
from tests.unit.test_vnext_cas_publication import SPACE, _parsed_parent, genesis_command
from tests.unit.test_vnext_governed_materialization import _lab_descriptors, _meta

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _publication(parent_revision_id: str) -> GovernedPublicationIdentity:
    return GovernedPublicationIdentity(
        operation_ids=("op:prospective",),
        created_at=NOW,
        expected_parent_revision_id=parent_revision_id,
    )


def _contribution(items: list) -> ProspectiveKnowledgeContribution:
    return ProspectiveKnowledgeContribution(
        contribution_id="contrib:prospective",
        space_id=SPACE,
        producer="producer:lab",
        produced_at=NOW,
        status="finalized",
        items=items,
    )


def _accepted(*item_ids: str) -> list[ContributionDisposition]:
    return [
        ContributionDisposition(item_id=item_id, disposition="accepted")
        for item_id in item_ids
    ]


def _entity(item_id: str = "create-1", client_op_id: str = "entity-op"):
    return ProspectiveCreateEntity(item_id=item_id, client_op_id=client_op_id)


def _assertion(
    *,
    item_id: str = "assert-1",
    client_op_id: str = "assertion-op",
    subject=None,
    value=None,
    predicate: str = "lab:reports_to",
):
    return ProspectiveCreateAssertion(
        item_id=item_id,
        client_op_id=client_op_id,
        subject=subject or ProspectiveEntityRef(client_op_id="entity-op"),
        predicate=predicate,
        value=value
        or ProspectiveEntityRefValue(entity=DurableEntityRef(entity_id="ent:alice")),
        metadata=_meta(),
    )


def _setup():
    repo = InMemoryKnowledgeRevisionRepository()
    repo.publish_revision(genesis_command())
    parent = _parsed_parent(repo)
    return repo, parent


def _publish(repo, parent, contribution, dispositions, publication_id="prepared:witness"):
    contract, profile = _lab_descriptors()
    return publish_prospective_contribution(
        parent=parent,
        prospective_contribution=contribution,
        dispositions=dispositions,
        publication=_publication(parent.revision_id),
        publication_id=publication_id,
        domain_contract=contract,
        semantic_profile=profile,
        repository=repo,
    )


def test_allocator_is_deterministic_type_separated_and_pinned() -> None:
    material = {
        "space_id": SPACE,
        "publication_id": "prepared:witness",
        "client_op_id": "entity-op",
    }
    entity = allocate_prospective_result_id(**material, result_kind="entity")
    assertion = allocate_prospective_result_id(**material, result_kind="assertion")
    assert entity == "ent:2cdbb234f97f9ef1b936ffdf9c35d95d"
    assert assertion == "asrt:a35c1291c57962255e1082b47d778cf7"
    assert allocate_prospective_result_id(**material, result_kind="entity") == entity
    assert entity != assertion
    assert allocate_prospective_result_id(
        **{**material, "space_id": "space:other"}, result_kind="entity"
    ) != entity
    assert allocate_prospective_result_id(
        **{**material, "publication_id": "prepared:other"}, result_kind="entity"
    ) != entity
    assert allocate_prospective_result_id(
        **{**material, "client_op_id": "other-op"}, result_kind="entity"
    ) != entity


def test_prospective_contract_schema_digest_is_pinned() -> None:
    models = (
        DurableEntityRef,
        ProspectiveEntityRef,
        ProspectiveEntityRefValue,
        ProspectiveCreateEntity,
        ProspectiveCreateAssertion,
        ProspectiveKnowledgeContribution,
        ProspectiveResultBinding,
        KnowledgeProspectivePublicationResult,
        KnowledgeProspectivePublication,
    )
    digest = canonical_sha256(
        {model.__name__: model.model_json_schema() for model in models}
    )
    assert digest == "d39ab66ce8e961b9868b961774ce5847bc5396efcdc677aaf4ecd6aa99050db5"


def test_prospective_result_contract_requires_sorted_unique_typed_bindings() -> None:
    digest = "1" * 64
    with pytest.raises(ValidationError, match="ordered"):
        KnowledgeProspectivePublicationResult(
            space_id=SPACE,
            publication_id="prepared:1",
            prospective_request_sha256=digest,
            published_revision_id="rev:1",
            results=[
                ProspectiveResultBinding(
                    client_op_id="z", result_kind="entity", durable_id="ent:z"
                ),
                ProspectiveResultBinding(
                    client_op_id="a", result_kind="assertion", durable_id="asrt:a"
                ),
            ],
        )
    with pytest.raises(ValidationError, match="must start"):
        ProspectiveResultBinding(
            client_op_id="a", result_kind="entity", durable_id="asrt:not-entity"
        )


def test_resolver_substitutes_one_entity_and_dependent_assertion() -> None:
    _repo, parent = _setup()
    contribution = _contribution([_entity(), _assertion()])
    resolved = resolve_prospective_contribution(
        prospective_contribution=contribution,
        dispositions=_accepted("create-1", "assert-1"),
        publication_id="prepared:witness",
        publication=_publication(parent.revision_id),
        parent=parent,
    )
    entity_item, assertion_item = resolved.canonical_contribution.items
    entity_id = entity_item.entity.entity_id  # type: ignore[union-attr]
    assertion = assertion_item.assertion  # type: ignore[union-attr]
    assert assertion.subject_entity_id == entity_id
    assert assertion.value.entity_id == "ent:alice"  # type: ignore[union-attr]
    assert [item.client_op_id for item in resolved.committed_result_bindings] == [
        "assertion-op",
        "entity-op",
    ]
    serialized = resolved.canonical_contribution.model_dump_json()
    assert "result_of" not in serialized
    assert "client_op_id" not in serialized


def test_two_references_to_same_result_resolve_to_same_id() -> None:
    _repo, parent = _setup()
    contribution = _contribution(
        [
            _entity(),
            _assertion(),
            _assertion(
                item_id="assert-2",
                client_op_id="assertion-op-2",
                value=ProspectiveEntityRefValue(
                    entity=ProspectiveEntityRef(client_op_id="entity-op")
                ),
            ),
        ]
    )
    resolved = resolve_prospective_contribution(
        prospective_contribution=contribution,
        dispositions=_accepted("create-1", "assert-1", "assert-2"),
        publication_id="prepared:two-refs",
        publication=_publication(parent.revision_id),
        parent=parent,
    )
    entity_id = resolved.canonical_contribution.items[0].entity.entity_id  # type: ignore[union-attr]
    first = resolved.canonical_contribution.items[1].assertion  # type: ignore[union-attr]
    second = resolved.canonical_contribution.items[2].assertion  # type: ignore[union-attr]
    assert first.subject_entity_id == entity_id
    assert second.subject_entity_id == entity_id
    assert second.value.entity_id == entity_id  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("items", "reason"),
    [
        ([_entity(), _entity("create-2", "entity-op")], "duplicate_client_op_id"),
        (
            [
                _assertion(
                    subject=ProspectiveEntityRef(client_op_id="missing"),
                )
            ],
            "unknown_result_of",
        ),
        (
            [
                _assertion(
                    item_id="producer",
                    client_op_id="assertion-handle",
                    subject=DurableEntityRef(entity_id="ent:alice"),
                    value=LiteralValue(value="value"),
                    predicate="lab:title",
                ),
                _assertion(
                    item_id="consumer",
                    client_op_id="consumer-handle",
                    subject=ProspectiveEntityRef(client_op_id="assertion-handle"),
                ),
            ],
            "result_of_wrong_kind",
        ),
    ],
)
def test_invalid_handles_fail_closed(items, reason) -> None:
    _repo, parent = _setup()
    contribution = _contribution(items)
    with pytest.raises(ProspectivePublicationIntegrityError) as exc:
        resolve_prospective_contribution(
            prospective_contribution=contribution,
            dispositions=_accepted(*(item.item_id for item in items)),
            publication_id="prepared:invalid",
            publication=_publication(parent.revision_id),
            parent=parent,
        )
    assert exc.value.reason == reason


def test_accepted_assertion_cannot_depend_on_rejected_create() -> None:
    _repo, parent = _setup()
    contribution = _contribution([_entity(), _assertion()])
    dispositions = [
        ContributionDisposition(item_id="create-1", disposition="rejected"),
        ContributionDisposition(item_id="assert-1", disposition="accepted"),
    ]
    with pytest.raises(ProspectivePublicationIntegrityError) as exc:
        resolve_prospective_contribution(
            prospective_contribution=contribution,
            dispositions=dispositions,
            publication_id="prepared:rejected-dependency",
            publication=_publication(parent.revision_id),
            parent=parent,
        )
    assert exc.value.reason == "accepted_dependency_not_accepted"


def test_rejected_items_create_no_graph_objects_or_result_bindings() -> None:
    repo, parent = _setup()
    contribution = _contribution([_entity()])
    result = _publish(
        repo,
        parent,
        contribution,
        [ContributionDisposition(item_id="create-1", disposition="rejected")],
        "prepared:rejected",
    )
    assert result.prospective_result.results == []
    stored = repo.get_revision(SPACE, result.publication_receipt.published_revision_id)
    assert stored is not None
    assert len(stored.graph_payload["entities"]) == 1


def test_allocator_collision_fails_create_new(monkeypatch) -> None:
    _repo, parent = _setup()
    monkeypatch.setattr(
        "dungeonmind.application.vnext.prospective.allocate_prospective_result_id",
        lambda **_kwargs: "ent:alice",
    )
    with pytest.raises(ProspectivePublicationIntegrityError) as exc:
        resolve_prospective_contribution(
            prospective_contribution=_contribution([_entity()]),
            dispositions=_accepted("create-1"),
            publication_id="prepared:collision",
            publication=_publication(parent.revision_id),
            parent=parent,
        )
    assert exc.value.reason == "identity_allocation_collision"


def test_worldkeeper_shape_publishes_and_exact_replay_is_stable() -> None:
    repo, parent = _setup()
    contribution = _contribution(
        [
            _entity(client_op_id="npc-7"),
            _assertion(
                client_op_id="rel-4",
                subject=ProspectiveEntityRef(client_op_id="npc-7"),
            ),
        ]
    )
    dispositions = _accepted("create-1", "assert-1")
    first = _publish(repo, parent, contribution, dispositions)
    event_count = len(repo.head_events(SPACE))
    second = _publish(repo, parent, contribution, dispositions)
    assert second == first
    assert len(repo.head_events(SPACE)) == event_count
    bindings = {
        item.client_op_id: item.durable_id for item in first.prospective_result.results
    }
    stored = repo.get_revision(SPACE, first.publication_receipt.published_revision_id)
    assert stored is not None
    assertion = next(
        item
        for item in stored.graph_payload["assertions"]
        if item["assertion_id"] == bindings["rel-4"]
    )
    assert assertion["subject_entity_id"] == bindings["npc-7"]
    assert assertion["value"]["entity_id"] == "ent:alice"


def test_changed_request_and_plain_v53_claim_conflict() -> None:
    repo, parent = _setup()
    contribution = _contribution([_entity()])
    _publish(repo, parent, contribution, _accepted("create-1"), "prepared:claimed")
    changed = _contribution([_entity(client_op_id="changed")])
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        _publish(repo, parent, changed, _accepted("create-1"), "prepared:claimed")

    plain_repo, plain_parent = _setup()
    resolved = resolve_prospective_contribution(
        prospective_contribution=contribution,
        dispositions=_accepted("create-1"),
        publication_id="prepared:plain",
        publication=_publication(plain_parent.revision_id),
        parent=plain_parent,
    )
    contract, profile = _lab_descriptors()
    from dungeonmind.application.vnext.materialization import materialize_governed_revision

    materialized = materialize_governed_revision(
        parent=plain_parent,
        contribution=resolved.canonical_contribution,
        dispositions=_accepted("create-1"),
        publication=_publication(plain_parent.revision_id),
        domain_contract=contract,
        semantic_profile=profile,
    )
    plain_repo.publish_publication(materialized.command, "prepared:plain")
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        _publish(
            plain_repo,
            plain_parent,
            contribution,
            _accepted("create-1"),
            "prepared:plain",
        )


def test_invalid_substituted_child_causes_zero_publication_mutation() -> None:
    repo, parent = _setup()
    before = (repo.get_head(SPACE), repo.head_events(SPACE))
    contribution = _contribution(
        [_entity(), _assertion(predicate="unknown:predicate")]
    )
    with pytest.raises(GovernedMaterializationIntegrityError):
        _publish(repo, parent, contribution, _accepted("create-1", "assert-1"))
    assert repo.get_head(SPACE) == before[0]
    assert repo.head_events(SPACE) == before[1]


def test_post_commit_response_loss_recovers_exact_mapping() -> None:
    lost = True

    def lose_response() -> None:
        nonlocal lost
        if lost:
            lost = False
            raise RuntimeError("response lost")

    repo = InMemoryKnowledgeRevisionRepository(after_publication_commit=lose_response)
    repo.publish_revision(genesis_command())
    parent = _parsed_parent(repo)
    result = _publish(
        repo,
        parent,
        _contribution([_entity()]),
        _accepted("create-1"),
        "prepared:response-loss",
    )
    assert result.prospective_result.results[0].client_op_id == "entity-op"


def test_ambiguous_publish_and_probe_returns_retry_safe_unknown() -> None:
    real, parent = _setup()

    class Unavailable:
        def publish_prospective_publication(self, *args):
            raise RuntimeError("publish unavailable")

        def get_prospective_publication(self, *args):
            raise RuntimeError("probe unavailable")

    contract, profile = _lab_descriptors()
    with pytest.raises(KnowledgePublicationOutcomeUnknownError) as exc:
        publish_prospective_contribution(
            parent=parent,
            prospective_contribution=_contribution([_entity()]),
            dispositions=_accepted("create-1"),
            publication=_publication(parent.revision_id),
            publication_id="prepared:unknown",
            domain_contract=contract,
            semantic_profile=profile,
            repository=cast(Any, Unavailable()),
        )
    assert exc.value.retry_safe is True
    assert real.get_prospective_publication(SPACE, "prepared:unknown") is None


def test_result_corruption_fails_closed() -> None:
    repo, parent = _setup()
    result = _publish(
        repo,
        parent,
        _contribution([_entity()]),
        _accepted("create-1"),
        "prepared:corrupt",
    )
    key = (SPACE, "prepared:corrupt")
    original = repo._prospective_results[key]
    repo._prospective_results[key] = original.model_copy(
        update={"prospective_request_sha256": canonical_sha256({"tampered": True})}
    )
    with pytest.raises(PersistenceIntegrityError, match="fingerprint"):
        _publish(
            repo,
            parent,
            _contribution([_entity()]),
            _accepted("create-1"),
            result.publication_receipt.publication_id,
        )

    tampered_binding = original.results[0].model_copy(update={"durable_id": "ent:tampered"})
    tampered_result = original.model_copy(update={"results": [tampered_binding]})
    repo._prospective_results[key] = tampered_result
    repo._prospective_fingerprints[key] = canonical_sha256(
        tampered_result.model_dump(mode="json")
    )
    with pytest.raises(PersistenceIntegrityError, match="allocation drift"):
        get_prospective_publication(SPACE, "prepared:corrupt", repository=repo)
