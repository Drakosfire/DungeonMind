"""Atomic prospective aliases; no new source or mutable-source admission path."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import replace

from dungeonmind.contracts.vnext.contribution import ContributionDisposition
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, SemanticProfileDescriptorV2
from dungeonmind.contracts.vnext.knowledge import IdentityAlias, PublishKnowledgeRevisionCommand
from dungeonmind.contracts.vnext.prospective import KnowledgeProspectivePublication
from dungeonmind.contracts.vnext.prospective_aliases import ProspectiveAliasContributionV1
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.canonical import canonical_json, canonical_sha256

from .errors import RevisionStructuralIntegrityError
from .materialization import (
    GovernedMaterializationResult,
    GovernedPublicationIdentity,
    _close_identity_decision_ids,
    _rebuild_child,
    _validate_child_vocabulary,
)
from .model import ParsedKnowledgeRevision
from .ports import KnowledgeRevisionRepository
from .prospective import (
    ResolvedProspectiveContribution,
    _fail,
    _plan_prospective_publication,
    _publish_planned_prospective_publication,
)


def _plan_prospective_alias_contribution(
    *,
    parent: ParsedKnowledgeRevision,
    request: ProspectiveAliasContributionV1,
    dispositions: Sequence[ContributionDisposition],
    publication: GovernedPublicationIdentity,
    publication_id: str,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
    admitted_evidence: Sequence[EvidenceRefV3] = (),
) -> tuple[
    GovernedMaterializationResult, ResolvedProspectiveContribution, PublishKnowledgeRevisionCommand
]:
    # Snapshot and revalidate nested mutable wire models before doing any work.
    request = ProspectiveAliasContributionV1.model_validate(request.model_dump(mode="json"))
    decisions = [
        ContributionDisposition.model_validate(d.model_dump(mode="json")) for d in dispositions
    ]
    item_ids = {item.item_id for item in request.contribution.items} | {
        a.item_id for a in request.aliases
    }
    decision_ids = [d.item_id for d in decisions]
    if len(decision_ids) != len(set(decision_ids)) or set(decision_ids) != item_ids:
        _fail("alias_disposition_inventory_mismatch")
    if any(d.disposition == "unresolved" for d in decisions):
        _fail("alias_unresolved_disposition")
    alias_item_ids = {alias.item_id for alias in request.aliases}
    base, resolved, base_command = _plan_prospective_publication(
        parent=parent,
        prospective_contribution=request.contribution,
        dispositions=[d for d in decisions if d.item_id not in alias_item_ids],
        publication=publication,
        publication_id=publication_id,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
        admitted_evidence=admitted_evidence,
    )
    _close_identity_decision_ids(resolved.canonical_contribution, decisions)
    started = time.perf_counter()
    decisions_by_id = {d.item_id: d.disposition for d in decisions}
    bindings = {b.client_op_id: b for b in resolved.committed_result_bindings}
    payload = base_command.graph_payload
    aliases = {a["alias_id"]: a for a in payload["aliases"]}
    accepted, rejected = list(base.accepted_item_ids), list(base.rejected_item_ids)
    admitted_evidence_ids = {e.evidence_ref_id for e in admitted_evidence}
    for item in request.aliases:
        if decisions_by_id[item.item_id] != "accepted":
            rejected.append(item.item_id)
            continue
        target = bindings.get(item.entity.client_op_id)
        if target is None or target.result_kind != "entity":
            _fail("alias_target_not_accepted_entity_create", item_id=item.item_id)
        if item.alias_id in aliases or item.alias_id in parent.aliases_by_id:
            _fail("alias_create_identity_collision", alias_id=item.alias_id)
        if any(
            identifier not in parent.evidence_by_id
            and identifier not in admitted_evidence_ids
            for identifier in item.evidence_ref_ids
        ):
            _fail("alias_evidence_not_in_parent", item_id=item.item_id)
        aliases[item.alias_id] = IdentityAlias(
            alias_id=item.alias_id,
            entity_id=target.durable_id,
            alias_text=item.alias_text,
            evidence_ref_ids=list(item.evidence_ref_ids),
            standing=item.standing,
        ).model_dump(mode="json")
        accepted.append(item.item_id)
    payload["aliases"] = [aliases[key] for key in sorted(aliases)]
    payload_sha = canonical_sha256(payload)
    try:
        child = _rebuild_child(
            parent=parent, publication=publication, payload=payload, payload_sha=payload_sha
        )
    except RevisionStructuralIntegrityError as exc:
        _fail("alias_child_structural_integrity", message=str(exc))
    _validate_child_vocabulary(
        child, domain_contract=domain_contract, semantic_profile=semantic_profile
    )
    command = PublishKnowledgeRevisionCommand.model_validate(
        {
            **base_command.model_dump(mode="json"),
            "graph_payload": payload,
        }
    )
    sealed = replace(
        base,
        graph_payload_sha256=payload_sha,
        accepted_item_ids=tuple(accepted),
        rejected_item_ids=tuple(rejected),
        validate_ms=base.validate_ms + (time.perf_counter() - started) * 1000,
        _command_json=canonical_json(command.model_dump(mode="json")),
        _payload_json=canonical_json(payload),
    )
    request_sha = canonical_sha256(
        {
            "schema": "dm_prospective_alias_request_identity_v1",
            "publication_id": publication_id,
            "request": request.model_dump(mode="json"),
            "dispositions": [
                d.model_dump(mode="json") for d in sorted(decisions, key=lambda d: d.item_id)
            ],
            "base_request_sha256": resolved.prospective_request_sha256,
        }
    )
    return sealed, replace(resolved, prospective_request_sha256=request_sha), command


def publish_prospective_alias_contribution(
    *,
    parent: ParsedKnowledgeRevision,
    request: ProspectiveAliasContributionV1,
    dispositions: Sequence[ContributionDisposition],
    publication: GovernedPublicationIdentity,
    publication_id: str,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
    repository: KnowledgeRevisionRepository,
) -> KnowledgeProspectivePublication:
    """Publish one fully validated entity/alias child through existing recovery.

    Evidence IDs must belong to the immutable parent. This does not authorize
    current source access; reads continue to revalidate mutable source authority.
    """
    materialization, resolved, command = _plan_prospective_alias_contribution(
        parent=parent,
        request=request,
        dispositions=dispositions,
        publication=publication,
        publication_id=publication_id,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
    )
    return _publish_planned_prospective_publication(
        materialization=materialization,
        resolved=resolved,
        command=command,
        publication_id=publication_id,
        repository=repository,
    )
