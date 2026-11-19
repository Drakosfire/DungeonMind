"""Atomic aliases preserve prospective identity, provenance and replay intent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dungeonmind.application.vnext.admission import AlwaysAdmitPolicy
from dungeonmind.application.vnext.entity_reads import EntityReadService
from dungeonmind.application.vnext.errors import (
    KnowledgePublicationIdempotencyConflictError,
    ProspectivePublicationIntegrityError,
)
from dungeonmind.application.vnext.prospective_aliases import (
    _plan_prospective_alias_contribution,
    publish_prospective_alias_contribution,
)
from dungeonmind.application.vnext.provenance import InMemoryKnowledgeSourceReader
from dungeonmind.application.vnext.read_context import KnowledgeReadContext
from dungeonmind.contracts.vnext.common import (
    KnowledgeStanding,
    LabelsAnyVisibility,
    PublicVisibility,
    ScopeBinding,
    ScopeSelector,
)
from dungeonmind.contracts.vnext.contribution import ContributionDisposition
from dungeonmind.contracts.vnext.projection import ProjectionRequest
from dungeonmind.contracts.vnext.prospective import (
    ProspectiveEntityRef,
    ProspectiveKnowledgeContribution,
)
from dungeonmind.contracts.vnext.prospective_aliases import (
    ProspectiveAliasContributionV1,
    ProspectiveCreateAliasV1,
)
from dungeonmind.contracts.vnext.source import SourceArtifactV3, SourceRevisionV2
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.unit.test_vnext_cas_publication import SPACE, _parsed_parent
from tests.unit.test_vnext_governed_materialization import _lab_descriptors
from tests.unit.test_vnext_prospective_publication import (
    NOW,
    _accepted,
    _assertion,
    _contribution,
    _entity,
    _publication,
    _setup,
)


def alias_request(text="  Exact Alias  ", standing=KnowledgeStanding.ESTABLISHED):
    return ProspectiveAliasContributionV1(
        contribution=_contribution([_entity(), _assertion()]),
        aliases=[
            ProspectiveCreateAliasV1(
                item_id="alias-item",
                alias_id="alias:one",
                entity=ProspectiveEntityRef(client_op_id="entity-op"),
                alias_text=text,
                evidence_ref_ids=["ev:lab"],
                standing=standing,
            )
        ],
    )


def publish_alias(repo, parent, request=None, dispositions=None, publication_id="prepared:aliases"):
    contract, profile = _lab_descriptors()
    return publish_prospective_alias_contribution(
        parent=parent,
        request=request or alias_request(),
        dispositions=dispositions
        if dispositions is not None
        else _accepted("create-1", "assert-1", "alias-item"),
        publication=_publication(parent.revision_id),
        publication_id=publication_id,
        domain_contract=contract,
        semantic_profile=profile,
        repository=repo,
    )


def test_contract_is_additive_closed_and_schema_hash_bound():
    request = alias_request()
    wire = request.model_dump(mode="json")
    assert ProspectiveAliasContributionV1.model_validate(wire) == request
    with pytest.raises(ValidationError):
        ProspectiveKnowledgeContribution.model_validate(wire)
    for field, value in (
        ("extra", 1),
        ("evidence_ref_ids", []),
        ("evidence_ref_ids", ["ev:lab", "ev:lab"]),
        ("entity", {"kind": "durable_entity", "entity_id": "ent:guessed"}),
    ):
        alias = {**wire["aliases"][0], field: value}
        with pytest.raises(ValidationError):
            ProspectiveAliasContributionV1.model_validate({**wire, "aliases": [alias]})
    bundle = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "Docs/Contracts/vnext/dm_prospective_alias_contribution_v1.json"
        ).read_text()
    )
    digest = bundle.pop("aggregate_sha256")
    assert digest == canonical_sha256(bundle)
    for model, record in zip(
        (ProspectiveAliasContributionV1, ProspectiveCreateAliasV1), bundle["contracts"], strict=True
    ):
        assert record["schema"] == model.model_json_schema()


def test_publish_exact_alias_with_entity_and_replay_after_descendant():
    repo, parent = _setup()
    first = publish_alias(repo, parent)
    assert publish_alias(repo, parent) == first
    stored = repo.get_revision(SPACE, first.publication_receipt.published_revision_id)
    alias = stored.graph_payload["aliases"][0]
    target = next(
        binding.durable_id
        for binding in first.prospective_result.results
        if binding.result_kind == "entity"
    )
    assert alias["entity_id"] == target
    assert alias["alias_text"] == "  Exact Alias  "
    assert alias["evidence_ref_ids"] == ["ev:lab"]
    assert alias["standing"] == "established"
    child = _parsed_parent(repo)
    publish_alias(
        repo,
        child,
        alias_request("descendant").model_copy(
            update={
                "aliases": [
                    alias_request("descendant")
                    .aliases[0]
                    .model_copy(update={"alias_id": "alias:two"})
                ]
            }
        ),
        publication_id="prepared:descendant-alias",
    )
    descendant_head = repo.get_head(SPACE)
    assert publish_alias(repo, parent) == first
    assert repo.get_head(SPACE) == descendant_head


@pytest.mark.parametrize(
    "damage",
    [
        "unknown",
        "assertion",
        "rejected",
        "missing_evidence",
        "missing_disposition",
        "duplicate_disposition",
        "extra_disposition",
        "unresolved",
    ],
)
def test_invalid_alias_plan_is_zero_mutation(damage):
    repo, parent = _setup()
    before = repo.get_head(SPACE)
    request = alias_request()
    dispositions = _accepted("create-1", "assert-1", "alias-item")
    if damage in {"unknown", "assertion"}:
        request.aliases[0].entity.client_op_id = (
            "missing" if damage == "unknown" else "assertion-op"
        )
    elif damage == "rejected":
        # Reject the dependent assertion too so alias target is the failing boundary.
        dispositions = [
            ContributionDisposition(item_id=i, disposition="rejected")
            for i in ("create-1", "assert-1")
        ] + _accepted("alias-item")
    elif damage == "missing_evidence":
        request.aliases[0].evidence_ref_ids = ["ev:foreign"]
    elif damage == "missing_disposition":
        dispositions.pop()
    elif damage == "duplicate_disposition":
        dispositions.append(dispositions[-1])
    elif damage == "extra_disposition":
        dispositions += _accepted("extra")
    else:
        dispositions[-1] = ContributionDisposition(item_id="alias-item", disposition="unresolved")
    with pytest.raises(ProspectivePublicationIntegrityError):
        publish_alias(repo, parent, request, dispositions)
    assert repo.get_head(SPACE) == before
    assert repo.get_prospective_publication(SPACE, "prepared:aliases") is None


@pytest.mark.parametrize("change", ["text", "standing", "evidence", "rejected_reason"])
def test_full_alias_intent_binds_replay(change):
    repo, parent = _setup()
    request = alias_request()
    dispositions = _accepted("create-1", "assert-1", "alias-item")
    if change == "rejected_reason":
        dispositions[-1] = ContributionDisposition(
            item_id="alias-item", disposition="rejected", reason_code="first"
        )
    publish_alias(repo, parent, request, dispositions)
    if change == "text":
        request.aliases[0].alias_text = "different"
    elif change == "standing":
        request.aliases[0].standing = KnowledgeStanding.PROVISIONAL
    elif change == "evidence":
        # Different valid intent with same parent evidence via a second rejected alias.
        request.aliases.append(
            request.aliases[0].model_copy(
                update={
                    "item_id": "alias-rejected",
                    "alias_id": "alias:rejected",
                    "evidence_ref_ids": ["different"],
                }
            )
        )
        dispositions.append(
            ContributionDisposition(item_id="alias-rejected", disposition="rejected")
        )
    else:
        dispositions[-1].reason_code = "changed"
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish_alias(repo, parent, request, dispositions)


def test_sealed_final_command_is_isolated_from_input_and_returned_command():
    _repo, parent = _setup()
    request = alias_request()
    contract, profile = _lab_descriptors()
    materialized, _, command = _plan_prospective_alias_contribution(
        parent=parent,
        request=request,
        dispositions=_accepted("create-1", "assert-1", "alias-item"),
        publication=_publication(parent.revision_id),
        publication_id="prepared:aliases",
        domain_contract=contract,
        semantic_profile=profile,
    )
    request.aliases[0].alias_text = "mutated"
    command.graph_payload["aliases"].clear()
    materialized.command.graph_payload["aliases"].clear()
    assert materialized.command.graph_payload["aliases"][0]["alias_text"] == "  Exact Alias  "


def test_response_loss_recovers_exact_augmented_payload_and_detects_mutation():
    real, parent = _setup()

    class ResponseLoss:
        def __getattr__(self, name):
            return getattr(real, name)

        def publish_prospective_publication(self, command, *args):
            real.publish_prospective_publication(command, *args)
            command.graph_payload["aliases"].clear()
            raise RuntimeError("response lost")

    result = publish_alias(ResponseLoss(), parent)
    assert result == publish_alias(real, parent)
    assert (
        len(
            real.get_revision(
                SPACE, result.publication_receipt.published_revision_id
            ).graph_payload["aliases"]
        )
        == 1
    )


@pytest.mark.parametrize(
    "status,hidden,standing,scope_matches,expected",
    [
        ("active", False, KnowledgeStanding.ESTABLISHED, True, 1),
        ("active", True, KnowledgeStanding.ESTABLISHED, True, 0),
        ("retracted", False, KnowledgeStanding.ESTABLISHED, True, 0),
        ("active", False, KnowledgeStanding.PROVISIONAL, True, 0),
        ("active", False, KnowledgeStanding.ESTABLISHED, False, 1),
    ],
)
def test_actual_published_alias_uses_normal_source_and_standing_admission(
    status, hidden, standing, scope_matches, expected
):
    repo, parent = _setup()
    result = publish_alias(repo, parent, alias_request(standing=standing))
    target = next(
        b.durable_id for b in result.prospective_result.results if b.result_kind == "entity"
    )
    parsed = _parsed_parent(repo)
    contract, profile = _lab_descriptors()
    artifact = SourceArtifactV3(
        source_artifact_id="art:lab",
        source_classification="lab:document",
        current_revision_id="srcrev:lab",
        authority="primary",
        status=status,
        visibility=LabelsAnyVisibility(labels=["lab:hidden"]) if hidden else PublicVisibility(),
    )
    reader = InMemoryKnowledgeSourceReader(
        artifacts={"art:lab": artifact},
        revisions={
            "srcrev:lab": SourceRevisionV2(
                source_revision_id="srcrev:lab",
                source_artifact_id="art:lab",
                content_sha256="a" * 64,
                body_storage="inline",
                created_at=NOW,
            )
        },
    )

    def context():
        return KnowledgeReadContext(
            parsed=parsed,
            request=ProjectionRequest(
                space_id=SPACE,
                revision_id=parsed.revision_id,
                scope_selector=ScopeSelector(
                    include_unscoped=True,
                    bindings=[
                        ScopeBinding(axis="lab:scope", value="one" if scope_matches else "other")
                    ],
                ),
                audience_labels=[],
                standing_selector=[KnowledgeStanding.ESTABLISHED],
            ),
            domain_contract=contract,
            semantic_profile=profile,
            domain_policy=AlwaysAdmitPolicy(policy_id=contract.admission_policy_id),
            source_reader=reader,
        )

    service = EntityReadService()
    complete = service.get_complete_entity(context(), target)
    assert len(complete.aliases) == expected
    if not scope_matches:
        # IdentityAlias has no scope. Scope gates assertions/list membership,
        # while exact identity reads retain source-authorized global aliases.
        assert complete.assertions == ()
        listing, listed_aliases = service.list_entities_with_aliases(context())
        assert listing.entities == () and listed_aliases == ()
    # Same cached immutable graph, new coherent read after source withdrawal.
    reader._artifacts["art:lab"] = artifact.model_copy(update={"status": "retracted"})
    assert service.get_complete_entity(context(), target).aliases == ()


def test_repository_cannot_mutate_final_payload_without_integrity_failure():
    real, parent = _setup()

    class MutatingRepository:
        def __getattr__(self, name):
            return getattr(real, name)

        def publish_prospective_publication(self, command, *args):
            command.graph_payload["aliases"][0]["alias_text"] = "forged by adapter"
            return real.publish_prospective_publication(command, *args)

    with pytest.raises(PersistenceIntegrityError):
        publish_alias(MutatingRepository(), parent)


def test_alias_disposition_identity_references_must_close():
    from dungeonmind.application.vnext.errors import GovernedMaterializationIntegrityError

    repo, parent = _setup()
    decisions = _accepted("create-1", "assert-1", "alias-item")
    decisions[-1].identity_decision_ids = ["missing-decision"]
    with pytest.raises(GovernedMaterializationIntegrityError):
        publish_alias(repo, parent, dispositions=decisions)
    assert repo.get_head(SPACE).head_revision_id == parent.revision_id


def test_alias_cannot_overwrite_parent_or_base_generated_identity():
    from dungeonmind.contracts.vnext.contribution import ProposeIdentityDecision
    from dungeonmind.contracts.vnext.knowledge import IdentityDecisionKind, IdentityDecisionV3
    from tests.unit.test_vnext_prospective_publication import _publish

    repo, parent = _setup()
    identity = ProposeIdentityDecision(
        item_id="identity",
        decision=IdentityDecisionV3(
            decision_id="alias:one",
            space_id=SPACE,
            decision_kind=IdentityDecisionKind.ALIAS_ADD,
            subject_entity_ids=["ent:alice"],
            alias="old",
            created_at=NOW,
        ),
    )
    request = alias_request()
    request.contribution.items.append(identity)
    with pytest.raises(ProspectivePublicationIntegrityError) as error:
        publish_alias(
            repo, parent, request, _accepted("create-1", "assert-1", "identity", "alias-item")
        )
    assert error.value.reason == "alias_create_identity_collision"
    _publish(
        repo,
        parent,
        _contribution([identity]),
        _accepted("identity"),
        publication_id="prepared:old-alias",
    )
    parent = _parsed_parent(repo)
    with pytest.raises(ProspectivePublicationIntegrityError) as error:
        publish_alias(repo, parent)
    assert error.value.reason == "alias_create_identity_collision"


@pytest.mark.parametrize("change", ["target", "evidence", "evidence_order"])
def test_changed_accepted_alias_target_or_valid_evidence_conflicts(change):
    from dungeonmind.infrastructure.memory.vnext_knowledge import (
        InMemoryKnowledgeRevisionRepository,
    )
    from tests.unit.test_vnext_cas_publication import genesis_command

    repo = InMemoryKnowledgeRevisionRepository()
    command = genesis_command()
    command.graph_payload["evidence"].append(
        {**command.graph_payload["evidence"][0], "evidence_ref_id": "ev:second"}
    )
    repo.publish_revision(command)
    parent = _parsed_parent(repo)
    request = alias_request()
    request.contribution.items.append(_entity(item_id="create-2", client_op_id="other-entity"))
    if change == "evidence_order":
        request.aliases[0].evidence_ref_ids = ["ev:lab", "ev:second"]
    dispositions = _accepted("create-1", "create-2", "assert-1", "alias-item")
    first = publish_alias(repo, parent, request, dispositions)
    stored = repo.get_revision(SPACE, first.publication_receipt.published_revision_id)
    assert (
        stored.graph_payload["aliases"][0]["evidence_ref_ids"]
        == request.aliases[0].evidence_ref_ids
    )
    if change == "target":
        request.aliases[0].entity.client_op_id = "other-entity"
    elif change == "evidence":
        request.aliases[0].evidence_ref_ids = ["ev:second"]
    else:
        request.aliases[0].evidence_ref_ids.reverse()
    with pytest.raises(KnowledgePublicationIdempotencyConflictError):
        publish_alias(repo, parent, request, dispositions)
