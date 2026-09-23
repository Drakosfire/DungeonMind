"""Prospective identity allocation, substitution, and recoverable publication."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, NoReturn

from dungeonmind.contracts.vnext.contribution import (
    ContributionDisposition,
    KnowledgeContribution,
    ProposeAssertion,
    ProposeEntity,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    DomainContractDescriptor,
    Entity,
    EntityRefValue,
    SemanticProfileDescriptorV2,
)
from dungeonmind.contracts.vnext.prospective import (
    DurableEntityRef,
    KnowledgeProspectivePublication,
    ProspectiveCreateAssertion,
    ProspectiveCreateEntity,
    ProspectiveEntityRef,
    ProspectiveEntityRefValue,
    ProspectiveKnowledgeContribution,
    ProspectiveResultBinding,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import ImmutableRevisionConflictError, PersistenceIntegrityError

from .authority import revision_from_command
from .errors import (
    KnowledgePublicationIdempotencyConflictError,
    KnowledgePublicationOutcomeUnknownError,
    KnowledgeStaleParentRevisionError,
    ProspectivePublicationIntegrityError,
)
from .materialization import (
    GovernedMaterializationResult,
    GovernedPublicationIdentity,
    materialize_governed_revision,
)
from .model import ParsedKnowledgeRevision
from .ports import KnowledgeRevisionRepository
from .publication import _verify_receipt, get_publication_receipt

_IDENTITY_SCHEMA = "dm_prospective_result_identity_v1"
_REQUEST_SCHEMA = "dm_prospective_publication_request_identity_v1"


def _fail(reason: str, **details: Any) -> NoReturn:
    raise ProspectivePublicationIntegrityError(reason, details=details) from None


def _find_allocated_id(value: Any, allocated_ids: set[str]) -> str | None:
    """Find caller-supplied use of an ID reserved for prospective substitution."""
    if isinstance(value, str):
        return value if value in allocated_ids else None
    if isinstance(value, dict):
        for nested in value.values():
            found = _find_allocated_id(nested, allocated_ids)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_allocated_id(nested, allocated_ids)
            if found is not None:
                return found
    return None


@dataclass(frozen=True, slots=True)
class ResolvedProspectiveContribution:
    canonical_contribution: KnowledgeContribution
    committed_result_bindings: tuple[ProspectiveResultBinding, ...]
    prospective_request_sha256: str


def allocate_prospective_result_id(
    *,
    space_id: str,
    publication_id: str,
    client_op_id: str,
    result_kind: Literal["entity", "assertion"],
) -> str:
    """Return one deterministic, type-separated Kernel provisional ID."""
    if not all(value.strip() for value in (space_id, publication_id, client_op_id)):
        _fail("allocation_identity_blank")
    digest = canonical_sha256(
        {
            "schema": _IDENTITY_SCHEMA,
            "space_id": space_id,
            "publication_id": publication_id,
            "client_op_id": client_op_id,
            "result_kind": result_kind,
        }
    )
    prefix = "ent" if result_kind == "entity" else "asrt"
    return f"{prefix}:{digest[:32]}"


def validate_prospective_result_bindings(
    *,
    command_graph_payload: dict[str, Any],
    space_id: str,
    publication_id: str,
    result_bindings: Sequence[ProspectiveResultBinding],
) -> None:
    """Verify port-supplied mappings before repository authority can mutate."""
    entity_ids = {
        item.get("entity_id") for item in command_graph_payload.get("entities", [])
    }
    assertion_ids = {
        item.get("assertion_id")
        for item in command_graph_payload.get("assertions", [])
    }
    for binding in result_bindings:
        expected_id = allocate_prospective_result_id(
            space_id=space_id,
            publication_id=publication_id,
            client_op_id=binding.client_op_id,
            result_kind=binding.result_kind,
        )
        if binding.durable_id != expected_id:
            _fail(
                "prospective_result_allocation_mismatch",
                client_op_id=binding.client_op_id,
                durable_id=binding.durable_id,
                expected_durable_id=expected_id,
            )
        ids = entity_ids if binding.result_kind == "entity" else assertion_ids
        if binding.durable_id not in ids:
            _fail(
                "prospective_result_missing_from_command",
                client_op_id=binding.client_op_id,
                durable_id=binding.durable_id,
            )


def validate_prospective_result_absent_from_parent(
    *,
    parent_graph_payload: dict[str, Any],
    result_bindings: Sequence[ProspectiveResultBinding],
) -> None:
    """Preserve create-new semantics at the repository authority boundary."""
    parent_entity_ids = {
        item.get("entity_id") for item in parent_graph_payload.get("entities", [])
    }
    parent_assertion_ids = {
        item.get("assertion_id")
        for item in parent_graph_payload.get("assertions", [])
    }
    for binding in result_bindings:
        parent_ids = (
            parent_entity_ids
            if binding.result_kind == "entity"
            else parent_assertion_ids
        )
        if binding.durable_id in parent_ids:
            _fail(
                "identity_allocation_collision",
                client_op_id=binding.client_op_id,
                durable_id=binding.durable_id,
            )


def resolve_prospective_contribution(
    *,
    prospective_contribution: ProspectiveKnowledgeContribution,
    dispositions: Sequence[ContributionDisposition],
    publication_id: str,
    publication: GovernedPublicationIdentity,
    parent: ParsedKnowledgeRevision,
) -> ResolvedProspectiveContribution:
    """Resolve prospective syntax into one ordinary canonical contribution."""
    if prospective_contribution.space_id != parent.space_id:
        _fail("contribution_space_mismatch")
    if publication.expected_parent_revision_id != parent.revision_id:
        _fail("expected_parent_mismatch")
    if not publication_id.strip():
        _fail("publication_id_blank")

    items = list(prospective_contribution.items)
    item_ids = [item.item_id for item in items]
    disposition_ids = [item.item_id for item in dispositions]
    if len(disposition_ids) != len(set(disposition_ids)):
        _fail("duplicate_disposition_item_ids")
    if set(disposition_ids) != set(item_ids):
        _fail(
            "incomplete_dispositions",
            missing=sorted(set(item_ids) - set(disposition_ids)),
            extra=sorted(set(disposition_ids) - set(item_ids)),
        )
    disposition_by_item = {item.item_id: item.disposition for item in dispositions}

    producers: dict[str, ProspectiveCreateEntity | ProspectiveCreateAssertion] = {}
    allocated: dict[str, str] = {}
    for item in items:
        if not isinstance(item, (ProspectiveCreateEntity, ProspectiveCreateAssertion)):
            continue
        if item.client_op_id in producers:
            _fail("duplicate_client_op_id", client_op_id=item.client_op_id)
        producers[item.client_op_id] = item
        result_kind: Literal["entity", "assertion"] = (
            "entity" if isinstance(item, ProspectiveCreateEntity) else "assertion"
        )
        allocated[item.client_op_id] = allocate_prospective_result_id(
            space_id=parent.space_id,
            publication_id=publication_id,
            client_op_id=item.client_op_id,
            result_kind=result_kind,
        )

    def resolve_operand(
        operand: DurableEntityRef | ProspectiveEntityRef,
        *,
        dependent_item_id: str,
    ) -> str:
        if isinstance(operand, DurableEntityRef):
            if operand.entity_id not in parent.entities_by_id:
                _fail(
                    "durable_entity_not_in_parent",
                    item_id=dependent_item_id,
                    entity_id=operand.entity_id,
                )
            return operand.entity_id
        producer = producers.get(operand.client_op_id)
        if producer is None:
            _fail(
                "unknown_result_of",
                item_id=dependent_item_id,
                client_op_id=operand.client_op_id,
            )
        if not isinstance(producer, ProspectiveCreateEntity):
            _fail(
                "result_of_wrong_kind",
                item_id=dependent_item_id,
                client_op_id=operand.client_op_id,
            )
        if (
            disposition_by_item[dependent_item_id] == "accepted"
            and disposition_by_item[producer.item_id] != "accepted"
        ):
            _fail(
                "accepted_dependency_not_accepted",
                item_id=dependent_item_id,
                dependency_item_id=producer.item_id,
            )
        return allocated[operand.client_op_id]

    canonical_items: list[Any] = []
    bindings: list[ProspectiveResultBinding] = []
    allocated_ids = set(allocated.values())
    for item in items:
        accepted = disposition_by_item[item.item_id] == "accepted"
        if isinstance(item, ProspectiveCreateEntity):
            durable_id = allocated[item.client_op_id]
            if accepted and durable_id in parent.entities_by_id:
                _fail("identity_allocation_collision", durable_id=durable_id)
            canonical_items.append(
                ProposeEntity(item_id=item.item_id, entity=Entity(entity_id=durable_id))
            )
            if accepted:
                bindings.append(
                    ProspectiveResultBinding(
                        client_op_id=item.client_op_id,
                        result_kind="entity",
                        durable_id=durable_id,
                    )
                )
        elif isinstance(item, ProspectiveCreateAssertion):
            durable_id = allocated[item.client_op_id]
            if accepted and durable_id in parent.assertions_by_id:
                _fail("identity_allocation_collision", durable_id=durable_id)
            subject_id = resolve_operand(item.subject, dependent_item_id=item.item_id)
            value = item.value
            if isinstance(value, ProspectiveEntityRefValue):
                resolved_value = EntityRefValue(
                    entity_id=resolve_operand(value.entity, dependent_item_id=item.item_id)
                )
            else:
                resolved_value = value
            canonical_items.append(
                ProposeAssertion(
                    item_id=item.item_id,
                    assertion=Assertion(
                        assertion_id=durable_id,
                        subject_entity_id=subject_id,
                        predicate=item.predicate,
                        value=resolved_value,
                        metadata=item.metadata,
                    ),
                )
            )
            if accepted:
                bindings.append(
                    ProspectiveResultBinding(
                        client_op_id=item.client_op_id,
                        result_kind="assertion",
                        durable_id=durable_id,
                    )
                )
        else:
            predicted_id = _find_allocated_id(
                item.model_dump(mode="json"), allocated_ids
            )
            if predicted_id is not None:
                _fail(
                    "ordinary_item_targets_prospective_result",
                    item_id=item.item_id,
                    durable_id=predicted_id,
                )
            canonical_items.append(item)

    canonical = KnowledgeContribution(
        contribution_id=prospective_contribution.contribution_id,
        space_id=prospective_contribution.space_id,
        producer=prospective_contribution.producer,
        produced_at=prospective_contribution.produced_at,
        source_refs=list(prospective_contribution.source_refs),
        status=prospective_contribution.status,
        supersedes_contribution_id=prospective_contribution.supersedes_contribution_id,
        items=canonical_items,
        diagnostics=list(prospective_contribution.diagnostics),
    )
    ordered_bindings = tuple(sorted(bindings, key=lambda item: item.client_op_id))
    request_sha = canonical_sha256(
        {
            "schema": _REQUEST_SCHEMA,
            "publication_id": publication_id,
            "prospective_contribution": prospective_contribution.model_dump(mode="json"),
            "dispositions": [
                item.model_dump(mode="json")
                for item in sorted(dispositions, key=lambda value: value.item_id)
            ],
            "publication_identity": {
                "operation_ids": list(publication.operation_ids),
                "created_at": publication.created_at.isoformat(),
                "expected_parent_revision_id": publication.expected_parent_revision_id,
            },
        }
    )
    return ResolvedProspectiveContribution(
        canonical_contribution=canonical,
        committed_result_bindings=ordered_bindings,
        prospective_request_sha256=request_sha,
    )


def publish_prospective_contribution(
    *,
    parent: ParsedKnowledgeRevision,
    prospective_contribution: ProspectiveKnowledgeContribution,
    dispositions: Sequence[ContributionDisposition],
    publication: GovernedPublicationIdentity,
    publication_id: str,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
    repository: KnowledgeRevisionRepository,
) -> KnowledgeProspectivePublication:
    """Resolve, validate, and atomically publish one prospective contribution."""
    resolved = resolve_prospective_contribution(
        prospective_contribution=prospective_contribution,
        dispositions=dispositions,
        publication_id=publication_id,
        publication=publication,
        parent=parent,
    )
    materialization: GovernedMaterializationResult = materialize_governed_revision(
        parent=parent,
        contribution=resolved.canonical_contribution,
        dispositions=dispositions,
        publication=publication,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
    )
    command = materialization.command
    validate_prospective_result_bindings(
        command_graph_payload=command.graph_payload,
        space_id=command.space_id,
        publication_id=publication_id,
        result_bindings=resolved.committed_result_bindings,
    )
    expected_revision_id = revision_from_command(command).revision_id
    try:
        aggregate = repository.publish_prospective_publication(
            command,
            publication_id,
            resolved.prospective_request_sha256,
            resolved.committed_result_bindings,
        )
    except (
        KnowledgePublicationIdempotencyConflictError,
        KnowledgeStaleParentRevisionError,
        ImmutableRevisionConflictError,
        PersistenceIntegrityError,
    ):
        raise
    except Exception as exc:
        try:
            recovered = get_prospective_publication(
                command.space_id,
                publication_id,
                repository=repository,
            )
        except (
            KnowledgePublicationIdempotencyConflictError,
            KnowledgeStaleParentRevisionError,
            ImmutableRevisionConflictError,
            PersistenceIntegrityError,
        ):
            raise
        except Exception as probe_exc:
            raise KnowledgePublicationOutcomeUnknownError(
                space_id=command.space_id,
                publication_id=publication_id,
                expected_published_revision_id=expected_revision_id,
                reason=f"publish={type(exc).__name__}; probe={type(probe_exc).__name__}",
            ) from exc
        if recovered is None:
            raise KnowledgePublicationOutcomeUnknownError(
                space_id=command.space_id,
                publication_id=publication_id,
                expected_published_revision_id=expected_revision_id,
                reason=f"publish={type(exc).__name__}; result=missing",
            ) from exc
        aggregate = recovered
    return _verify_prospective_publication(
        aggregate,
        materialization=materialization,
        publication_id=publication_id,
        prospective_request_sha256=resolved.prospective_request_sha256,
        expected_bindings=resolved.committed_result_bindings,
        repository=repository,
    )


def get_prospective_publication(
    space_id: str,
    publication_id: str,
    *,
    repository: KnowledgeRevisionRepository,
) -> KnowledgeProspectivePublication | None:
    aggregate = repository.get_prospective_publication(space_id, publication_id)
    if aggregate is None:
        if get_publication_receipt(space_id, publication_id, repository=repository):
            raise KnowledgePublicationIdempotencyConflictError(
                space_id=space_id, publication_id=publication_id
            )
        return None
    result = aggregate.prospective_result
    if result.space_id != space_id or result.publication_id != publication_id:
        raise PersistenceIntegrityError("prospective result identity drift")
    receipt = get_publication_receipt(space_id, publication_id, repository=repository)
    if receipt is None or receipt != aggregate.publication_receipt:
        raise PersistenceIntegrityError("prospective result receipt mismatch")
    _verify_result_bindings(aggregate, repository=repository)
    return aggregate


def _verify_prospective_publication(
    aggregate: KnowledgeProspectivePublication,
    *,
    materialization: GovernedMaterializationResult,
    publication_id: str,
    prospective_request_sha256: str,
    expected_bindings: tuple[ProspectiveResultBinding, ...],
    repository: KnowledgeRevisionRepository,
) -> KnowledgeProspectivePublication:
    command = materialization.command
    _verify_receipt(
        aggregate.publication_receipt,
        command,
        publication_id=publication_id,
        repository=repository,
    )
    result = aggregate.prospective_result
    if result.prospective_request_sha256 != prospective_request_sha256:
        raise PersistenceIntegrityError("prospective request digest mismatch")
    if tuple(result.results) != expected_bindings:
        raise PersistenceIntegrityError("prospective result bindings mismatch")
    _verify_result_bindings(aggregate, repository=repository)
    return aggregate


def _verify_result_bindings(
    aggregate: KnowledgeProspectivePublication,
    *,
    repository: KnowledgeRevisionRepository,
) -> None:
    result = aggregate.prospective_result
    stored = repository.get_revision(result.space_id, result.published_revision_id)
    if stored is None:
        raise PersistenceIntegrityError("prospective result references missing revision")
    payload = stored.graph_payload
    entity_ids = {item.get("entity_id") for item in payload.get("entities", [])}
    assertion_ids = {item.get("assertion_id") for item in payload.get("assertions", [])}
    for binding in result.results:
        expected_id = allocate_prospective_result_id(
            space_id=result.space_id,
            publication_id=result.publication_id,
            client_op_id=binding.client_op_id,
            result_kind=binding.result_kind,
        )
        if binding.durable_id != expected_id:
            raise PersistenceIntegrityError("prospective result allocation drift")
        ids = entity_ids if binding.result_kind == "entity" else assertion_ids
        if binding.durable_id not in ids:
            raise PersistenceIntegrityError("prospective result binding missing from revision")
