"""The actual governed transition, including replay, failure and future admission."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace

import pytest

from dungeonmind.application.vnext import transition_knowledge_semantic_profile
from dungeonmind.application.vnext.builder import build_parsed_knowledge_revision
from dungeonmind.application.vnext.errors import (
    KnowledgeProfileTransitionIntegrityError,
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
)
from dungeonmind.application.vnext.materialization import decode_native_graph_payload
from dungeonmind.application.vnext.publication import publish_governed_materialization
from dungeonmind.contracts.vnext.domain import (
    SemanticProfileDescriptorV2,
    SemanticProfileDescriptorV3,
)
from dungeonmind.contracts.vnext.profile_transition import KnowledgeProfileTransitionV1
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from dungeonmind.infrastructure.memory.vnext_knowledge import InMemoryKnowledgeRevisionRepository
from tests.unit.test_vnext_cas_publication import NOW, SPACE, _origin, genesis_command
from tests.unit.test_vnext_governed_materialization import (
    _accepted,
    _call,
    _contribution,
    _lab_descriptors,
    _literal,
)


def fixture(repository=None, *, current_override=None, payload=None):
    repo = repository or InMemoryKnowledgeRevisionRepository()
    domain, current = _lab_descriptors()
    current = current_override or current
    target = SemanticProfileDescriptorV3.model_validate(
        current.model_dump(mode="json")
        | {
            "schema_version": "dm_semantic_profile_v3",
            "profile_revision": "2",
            "term_namespaces": ["lab", "custom"],
            "open_predicate_namespaces": [
                {"namespace": "custom", "allowed_value_kinds": ["literal"]}
            ],
        }
    )
    command = genesis_command(origin=_origin(), payload=payload)
    command = command.model_copy(
        update={
            "semantic_profile_ref": command.semantic_profile_ref.model_copy(
                update={
                    "profile_id": current.profile_id,
                    "profile_revision": current.profile_revision,
                    "descriptor_sha256": canonical_sha256(current.model_dump(mode="json")),
                }
            )
        }
    )
    parent = repo.publish_publication(command, "init")
    request = KnowledgeProfileTransitionV1(
        space_id=SPACE,
        expected_parent_revision_id=parent.published_revision_id,
        domain_contract_ref=repo.get_revision(
            SPACE, parent.published_revision_id
        ).revision.domain_contract_ref,
        from_profile_ref=repo.get_revision(
            SPACE, parent.published_revision_id
        ).revision.semantic_profile_ref,
        to_profile_ref={
            "profile_id": target.profile_id,
            "profile_revision": target.profile_revision,
            "descriptor_sha256": canonical_sha256(target.model_dump(mode="json")),
        },
        publication_id="profile-extension",
        created_at=NOW + timedelta(minutes=1),
    )
    return SimpleNamespace(
        repo=repo, domain=domain, current=current, target=target, request=request, parent=parent
    )


def transition(f, **changes):
    return transition_knowledge_semantic_profile(
        **(
            dict(
                repository=f.repo,
                request=f.request,
                domain_contract=f.domain,
                current_profile=f.current,
                target_profile=f.target,
            )
            | changes
        )
    )


def assert_preservation_and_future_publication(f):
    before = f.repo.get_revision(SPACE, f.parent.published_revision_id)
    receipt = transition(f)
    child = f.repo.get_revision(SPACE, receipt.published_revision_id)
    assert child.graph_payload == before.graph_payload
    assert child.graph_payload_sha256 == before.graph_payload_sha256
    assert child.revision.migration_origin_ref == before.revision.migration_origin_ref
    assert child.revision.domain_contract_ref == before.revision.domain_contract_ref
    assert child.revision.semantic_profile_ref == f.request.to_profile_ref
    assert f.repo.get_revision(SPACE, before.revision.revision_id) == before
    parsed = build_parsed_knowledge_revision(
        revision=child.revision, decoded_content=decode_native_graph_payload(child.graph_payload)
    )
    historical = build_parsed_knowledge_revision(
        revision=before.revision, decoded_content=decode_native_graph_payload(before.graph_payload)
    )
    assert parsed.assertions_by_id == historical.assertions_by_id
    assertion = _literal("asrt:custom", "ent:alice", "A new source-local relation")
    assertion = assertion.model_copy(update={"predicate": "custom:description"})
    from dungeonmind.contracts.vnext.contribution import ProposeAssertion

    item = ProposeAssertion(item_id="i1", assertion=assertion)
    contribution = _contribution(parsed, [item])
    materialization = _call(
        parent=parsed,
        contribution=contribution,
        dispositions=_accepted("i1"),
        semantic_profile=f.target,
    )
    published = publish_governed_materialization(
        materialization, repository=f.repo, publication_id="custom-child"
    )
    assert published.expected_parent_revision_id == receipt.published_revision_id
    assert transition(f) == receipt
    assert f.repo.get_head(SPACE).head_revision_id == published.published_revision_id
    return receipt


def test_populated_graph_preserved_history_replays_and_custom_publication_succeeds():
    assert_preservation_and_future_publication(fixture())


@pytest.mark.parametrize(
    "mutation",
    [
        "namespace",
        "unused_predicate",
        "literal_schema",
        "same_policy",
        "unrestricted_v2",
        "wrong_digest",
        "wrong_domain",
        "missing_parent",
    ],
)
def test_rejects_policy_or_authority_drift_without_writes(mutation):
    f = fixture()
    before = f.repo.get_head(SPACE)
    target = f.target.model_dump(mode="json")
    current = f.current.model_dump(mode="json")
    request = f.request
    if mutation == "namespace":
        target["term_namespaces"] = ["custom"]
    if mutation == "unused_predicate":
        target["predicates"] = target["predicates"][:1]
    if mutation == "literal_schema":
        target["predicates"][0]["literal_schema"] = {"type": "string"}
    if mutation == "same_policy":
        target = current | {"profile_revision": "2"}
    if mutation == "unrestricted_v2":
        current["predicates"] = []
    if mutation == "wrong_domain":
        request = request.model_copy(
            update={
                "domain_contract_ref": request.domain_contract_ref.model_copy(
                    update={"domain_revision": "other"}
                )
            }
        )
    if mutation == "missing_parent":
        request = request.model_copy(update={"expected_parent_revision_id": "rev:missing"})
    target_model = (
        SemanticProfileDescriptorV3
        if target["schema_version"].endswith("v3")
        else SemanticProfileDescriptorV2
    ).model_validate(target)
    current_model = SemanticProfileDescriptorV2.model_validate(current)
    request = request.model_copy(
        update={
            "to_profile_ref": request.to_profile_ref.model_copy(
                update={"descriptor_sha256": canonical_sha256(target_model.model_dump(mode="json"))}
            )
        }
    )
    if mutation == "wrong_digest":
        request = request.model_copy(
            update={
                "to_profile_ref": request.to_profile_ref.model_copy(
                    update={"descriptor_sha256": "0" * 64}
                )
            }
        )
    if mutation == "unrestricted_v2":
        request = request.model_copy(
            update={
                "from_profile_ref": request.from_profile_ref.model_copy(
                    update={
                        "descriptor_sha256": canonical_sha256(current_model.model_dump(mode="json"))
                    }
                )
            }
        )
    with pytest.raises(KnowledgeProfileTransitionIntegrityError):
        transition(f, request=request, current_profile=current_model, target_profile=target_model)
    assert f.repo.get_head(SPACE) == before
    assert f.repo.get_publication_receipt(SPACE, request.publication_id) is None


def test_exact_identity_conflicts_on_changed_timestamp_and_cas_on_competitor():
    f = fixture()
    receipt = transition(f)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        transition(
            f, request=f.request.model_copy(update={"created_at": NOW + timedelta(minutes=2)})
        )
    with pytest.raises(KnowledgeStaleParentRevisionError):
        transition(f, request=f.request.model_copy(update={"publication_id": "competing"}))
    assert f.repo.get_head(SPACE).head_revision_id == receipt.published_revision_id


def test_lost_ack_recovers_original_receipt():
    f = fixture()

    def lost():
        raise RuntimeError("ack lost")

    f.repo._after_publication_commit = lost
    receipt = transition(f)
    assert transition(f) == receipt
    assert len(f.repo.head_events(SPACE)) == 2


def test_missing_recovery_remains_unknown_and_corrupt_recovery_fails_closed():
    f = fixture()
    original = f.repo.publish_publication

    def unknown(*args):
        raise RuntimeError("transport failed before known result")

    f.repo.publish_publication = unknown
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        transition(f)
    f.repo.publish_publication = original
    receipt = transition(f)
    f.repo._receipts[(SPACE, f.request.publication_id)] = receipt.model_copy(
        update={"graph_payload_sha256": "0" * 64}
    )
    with pytest.raises(PersistenceIntegrityError):
        transition(f)


def test_concurrent_competitors_only_publish_one_child():
    f = fixture()

    def attempt(identity):
        try:
            return transition(f, request=f.request.model_copy(update={"publication_id": identity}))
        except KnowledgeStaleParentRevisionError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["one", "two"]))
    assert sum(r is not None for r in results) == 1
    assert len(f.repo.head_events(SPACE)) == 2


@pytest.mark.parametrize("removed", ["classification", "open_namespace", "open_value_kind"])
def test_unused_permissions_cannot_be_removed(removed):
    _, base = _lab_descriptors()
    if removed == "classification":
        current = base.model_copy(update={"classification_terms": ["lab:unused"]})
    else:
        current = SemanticProfileDescriptorV3.model_validate(
            base.model_dump(mode="json")
            | {
                "schema_version": "dm_semantic_profile_v3",
                "term_namespaces": ["lab", "unused"],
                "open_predicate_namespaces": [
                    {"namespace": "unused", "allowed_value_kinds": ["literal", "entity_ref"]}
                ],
            }
        )
    f = fixture(current_override=current)
    target = f.target.model_dump(mode="json")
    if removed == "classification":
        target["classification_terms"] = []
    # fixture target has already removed the old unused open namespace entirely.
    if removed == "open_value_kind":
        target["term_namespaces"].append("unused")
        target["open_predicate_namespaces"].append(
            {"namespace": "unused", "allowed_value_kinds": ["entity_ref"]}
        )
    target = SemanticProfileDescriptorV3.model_validate(target)
    request = f.request.model_copy(
        update={
            "to_profile_ref": f.request.to_profile_ref.model_copy(
                update={"descriptor_sha256": canonical_sha256(target.model_dump(mode="json"))}
            )
        }
    )
    before = f.repo.get_head(SPACE)
    with pytest.raises(KnowledgeProfileTransitionIntegrityError):
        transition(f, request=request, target_profile=target)
    assert f.repo.get_head(SPACE) == before


def test_existing_graph_is_validated_against_target_vocabulary():
    from tests.unit.test_vnext_cas_publication import _alice_payload

    payload = _alice_payload()
    payload["assertions"][0]["predicate"] = "lab:undeclared"
    f = fixture(payload=payload)
    with pytest.raises(
        KnowledgeProfileTransitionIntegrityError, match="native profile transition failed"
    ):
        transition(f)
    assert f.repo.get_head(SPACE).head_revision_id == f.parent.published_revision_id


def test_unavailable_recovery_stays_unknown_without_second_operation():
    f = fixture()
    calls = []

    def unavailable(*args):
        calls.append(args)
        raise RuntimeError("unavailable")

    f.repo.publish_publication = unavailable
    f.repo.get_publication_receipt = unavailable
    with pytest.raises(KnowledgePublicationOutcomeUnknownError):
        transition(f)
    assert len(calls) == 2
    assert f.repo.get_head(SPACE).head_revision_id == f.parent.published_revision_id


def test_reusing_publication_id_for_later_parent_and_target_conflicts():
    f = fixture()
    first = transition(f)
    third = f.target.model_dump(mode="json")
    third["profile_revision"] = "3"
    third["open_predicate_namespaces"][0]["allowed_value_kinds"].append("entity_ref")
    third = SemanticProfileDescriptorV3.model_validate(third)
    request = f.request.model_copy(
        update={
            "expected_parent_revision_id": first.published_revision_id,
            "from_profile_ref": f.request.to_profile_ref,
            "to_profile_ref": f.request.to_profile_ref.model_copy(
                update={
                    "profile_revision": "3",
                    "descriptor_sha256": canonical_sha256(third.model_dump(mode="json")),
                }
            ),
        }
    )
    before = f.repo.get_head(SPACE)
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        transition(f, request=request, current_profile=f.target, target_profile=third)
    assert f.repo.get_head(SPACE) == before
    assert f.repo.get_publication_receipt(SPACE, request.publication_id) == first
