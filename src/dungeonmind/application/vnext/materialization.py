"""Generic governed materialization of one native-vNext child graph.

Given one exact native parent revision, one frozen KnowledgeContribution,
complete accepted/rejected dispositions, pinned DomainContract/SemanticProfile
descriptors, and explicit publication identity, this module produces one
structurally and vocabulary-validated child payload and one sealed
PublishKnowledgeRevisionCommand. It does not write a repository, mutate a
head, perform CAS publication, or import World/Graph-Review transport.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NoReturn

from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    DomainMetadataEntry,
    DomainTemporalScope,
    EpistemicBasis,
    KnowledgeStanding,
    LabelsAllVisibility,
    LabelsAnyVisibility,
    PublicVisibility,
    ScopeBinding,
    TimelessTemporalScope,
    UnknownTemporalScope,
    UtcIntervalTemporalScope,
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
    SemanticProfileDescriptorV2,
    TermRefValue,
)
from dungeonmind.contracts.vnext.knowledge import (
    IdentityAlias,
    IdentityDecisionKind,
    IdentityDecisionV3,
    KnowledgeRevision,
    MigrationOriginRef,
    PublishKnowledgeRevisionCommand,
)
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.canonical import canonical_json, canonical_sha256

from .admission import domain_declaration_passes, semantic_profile_passes
from .builder import DecodedKnowledgeContent, build_parsed_knowledge_revision
from .errors import GovernedMaterializationIntegrityError, RevisionStructuralIntegrityError
from .frozen_json import thaw_json_value
from .model import ParsedKnowledgeRevision
from .records import (
    ParsedAssertion,
    ParsedDomainTemporalScope,
    ParsedEntityRefValue,
    ParsedEvidenceRef,
    ParsedLabelsAllVisibility,
    ParsedLabelsAnyVisibility,
    ParsedLiteralValue,
    ParsedPublicVisibility,
    ParsedTermRefValue,
    ParsedTimelessTemporalScope,
    ParsedUnknownTemporalScope,
    ParsedUtcIntervalTemporalScope,
)

NATIVE_VNEXT_GRAPH_SCHEMA = "dm_vnext_graph_v1"
_CHILD_VALIDATION_REVISION_ID = "rev:v5-1-child-validation"
_FINALIZED = "finalized"
_MATERIALIZABLE_IDENTITY = frozenset(
    {
        IdentityDecisionKind.ALIAS_ADD,
        IdentityDecisionKind.ALIAS_REMOVE,
        IdentityDecisionKind.MERGE,
        IdentityDecisionKind.REJECT_CANDIDATE,
    }
)


def _fail(reason: str, **details: Any) -> NoReturn:
    raise GovernedMaterializationIntegrityError(reason, details=details) from None


@dataclass(frozen=True, slots=True)
class GovernedPublicationIdentity:
    """Caller-supplied identity for the unpublished child command."""

    operation_ids: tuple[str, ...]
    created_at: datetime
    expected_parent_revision_id: str


@dataclass(frozen=True, slots=True)
class GovernedMaterializationResult:
    """Ephemeral materialization with a sealed command snapshot.

    ``command`` and ``graph_payload`` are copy-on-read. Mutating a retrieved
    command cannot change a later retrieve or the bound payload digest.
    """

    graph_payload_sha256: str
    accepted_item_ids: tuple[str, ...]
    rejected_item_ids: tuple[str, ...]
    validate_ms: float
    serialize_hash_ms: float
    _command_json: str
    _payload_json: str

    @property
    def command(self) -> PublishKnowledgeRevisionCommand:
        loaded = json.loads(self._command_json)
        restored = PublishKnowledgeRevisionCommand.model_validate(loaded)
        if canonical_sha256(restored.graph_payload) != self.graph_payload_sha256:
            _fail("sealed_command_payload_digest_mismatch")
        return restored

    @property
    def graph_payload(self) -> dict[str, Any]:
        loaded = json.loads(self._payload_json)
        if not isinstance(loaded, dict):
            _fail("isolated_payload_not_object")
        return loaded


def materialize_governed_revision(
    *,
    parent: ParsedKnowledgeRevision,
    contribution: KnowledgeContribution,
    dispositions: Sequence[ContributionDisposition],
    publication: GovernedPublicationIdentity,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
) -> GovernedMaterializationResult:
    """Materialize one validated native child graph and publish command."""
    validate_started = time.perf_counter()
    _validate_preconditions(
        parent,
        contribution,
        dispositions,
        publication,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
    )
    validate_ms = (time.perf_counter() - validate_started) * 1000.0

    disposition_by_item = {item.item_id: item for item in dispositions}
    accepted_ids: list[str] = []
    rejected_ids: list[str] = []
    for item in contribution.items:
        disposition = disposition_by_item[item.item_id]
        if disposition.disposition == "accepted":
            accepted_ids.append(item.item_id)
        else:
            rejected_ids.append(item.item_id)

    entities = {entity.entity_id: entity for entity in _entities_from_parsed(parent)}
    assertions = {
        assertion.assertion_id: assertion for assertion in _assertions_from_parsed(parent)
    }
    aliases = {alias.alias_id: alias for alias in _aliases_from_parsed(parent)}
    evidence = {ref.evidence_ref_id: ref for ref in _evidence_from_parsed(parent)}

    for item in contribution.items:
        if disposition_by_item[item.item_id].disposition != "accepted":
            continue
        if isinstance(item, ProposeEntity):
            _apply_propose_entity(entities, item)
        elif isinstance(item, ProposeAssertion):
            _apply_propose_assertion(assertions, item)
        elif isinstance(item, RetractAssertion):
            _apply_retract(assertions, item)
        elif isinstance(item, SupersedeAssertion):
            _apply_supersede(assertions, item)
        elif isinstance(item, ProposeIdentityDecision):
            _apply_identity(entities, assertions, aliases, item, parent.space_id)
        else:
            _fail("unsupported_contribution_item", item_id=item.item_id)

    serialize_started = time.perf_counter()
    payload = encode_native_graph_payload(
        entities=entities,
        assertions=assertions,
        aliases=aliases,
        evidence=evidence,
    )
    payload_sha = canonical_sha256(payload)
    serialize_hash_ms = (time.perf_counter() - serialize_started) * 1000.0

    validate_started = time.perf_counter()
    try:
        child = _rebuild_child(
            parent=parent,
            publication=publication,
            payload=payload,
            payload_sha=payload_sha,
        )
    except RevisionStructuralIntegrityError as exc:
        _fail(
            "child_structural_integrity",
            message=str(exc),
        )
    _validate_child_vocabulary(
        child,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
    )
    validate_ms += (time.perf_counter() - validate_started) * 1000.0

    serialize_started = time.perf_counter()
    command = PublishKnowledgeRevisionCommand(
        space_id=parent.space_id,
        parent_revision_id=parent.revision_id,
        expected_parent_revision_id=parent.revision_id,
        operation_ids=list(publication.operation_ids),
        graph_schema=parent.graph_schema,
        graph_payload=json.loads(canonical_json(payload)),
        domain_contract_ref=_domain_contract_ref(parent),
        semantic_profile_ref=_semantic_profile_ref(parent),
        migration_origin_ref=_migration_origin_ref(parent),
        created_at=publication.created_at,
    )
    command_json = canonical_json(command.model_dump(mode="json"))
    payload_json = canonical_json(payload)
    serialize_hash_ms += (time.perf_counter() - serialize_started) * 1000.0
    return GovernedMaterializationResult(
        graph_payload_sha256=payload_sha,
        accepted_item_ids=tuple(accepted_ids),
        rejected_item_ids=tuple(rejected_ids),
        validate_ms=validate_ms,
        serialize_hash_ms=serialize_hash_ms,
        _command_json=command_json,
        _payload_json=payload_json,
    )


def encode_native_graph_payload(
    *,
    entities: Mapping[str, Entity],
    assertions: Mapping[str, Assertion],
    aliases: Mapping[str, IdentityAlias],
    evidence: Mapping[str, EvidenceRefV3],
) -> dict[str, Any]:
    """Deterministic native-vNext graph payload from contract primitives."""
    return {
        "entities": [entities[key].model_dump(mode="json") for key in sorted(entities)],
        "assertions": [assertions[key].model_dump(mode="json") for key in sorted(assertions)],
        "aliases": [aliases[key].model_dump(mode="json") for key in sorted(aliases)],
        "evidence": [evidence[key].model_dump(mode="json") for key in sorted(evidence)],
    }


def decode_native_graph_payload(payload: Mapping[str, Any]) -> DecodedKnowledgeContent:
    """Contract-validate a native-vNext graph payload."""
    try:
        entities = [Entity.model_validate(item) for item in payload["entities"]]
        assertions = [Assertion.model_validate(item) for item in payload["assertions"]]
        aliases = [IdentityAlias.model_validate(item) for item in payload["aliases"]]
        evidence = [EvidenceRefV3.model_validate(item) for item in payload["evidence"]]
    except (KeyError, TypeError, ValueError) as exc:
        _fail("native_payload_decode", message=str(exc))
    return DecodedKnowledgeContent(
        entities=tuple(entities),
        assertions=tuple(assertions),
        aliases=tuple(aliases),
        evidence=tuple(evidence),
        graph_schema=NATIVE_VNEXT_GRAPH_SCHEMA,
        graph_payload_sha256=canonical_sha256(dict(payload)),
    )


def _validate_preconditions(
    parent: ParsedKnowledgeRevision,
    contribution: KnowledgeContribution,
    dispositions: Sequence[ContributionDisposition],
    publication: GovernedPublicationIdentity,
    *,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
) -> None:
    if parent.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA:
        _fail("parent_not_native_vnext", graph_schema=parent.graph_schema)
    if contribution.space_id != parent.space_id:
        _fail(
            "contribution_space_mismatch",
            contribution_space_id=contribution.space_id,
            parent_space_id=parent.space_id,
        )
    if contribution.status != _FINALIZED:
        _fail("contribution_not_finalized", status=contribution.status)
    item_ids = [item.item_id for item in contribution.items]
    if len(item_ids) != len(set(item_ids)):
        _fail("duplicate_contribution_item_ids")
    disposition_ids = [item.item_id for item in dispositions]
    if len(disposition_ids) != len(set(disposition_ids)):
        _fail("duplicate_disposition_item_ids")
    if set(disposition_ids) != set(item_ids):
        _fail(
            "incomplete_dispositions",
            missing=sorted(set(item_ids) - set(disposition_ids)),
            extra=sorted(set(disposition_ids) - set(item_ids)),
        )
    unresolved = [item.item_id for item in dispositions if item.disposition == "unresolved"]
    if unresolved:
        _fail("unresolved_dispositions", item_ids=unresolved)
    if publication.expected_parent_revision_id != parent.revision_id:
        _fail(
            "expected_parent_mismatch",
            expected_parent_revision_id=publication.expected_parent_revision_id,
            parent_revision_id=parent.revision_id,
        )
    if not publication.operation_ids:
        _fail("empty_operation_ids")
    if len(publication.operation_ids) != len(set(publication.operation_ids)):
        _fail("duplicate_operation_ids")
    _pin_descriptors(
        parent,
        domain_contract=domain_contract,
        semantic_profile=semantic_profile,
    )
    _close_identity_decision_ids(contribution, dispositions)


def _pin_descriptors(
    parent: ParsedKnowledgeRevision,
    *,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
) -> None:
    contract_ref = parent.domain_contract_ref
    if (
        domain_contract.domain_id != contract_ref.domain_id
        or domain_contract.domain_revision != contract_ref.domain_revision
    ):
        _fail(
            "domain_contract_identity_mismatch",
            domain_id=domain_contract.domain_id,
            domain_revision=domain_contract.domain_revision,
            expected_domain_id=contract_ref.domain_id,
            expected_domain_revision=contract_ref.domain_revision,
        )
    contract_digest = canonical_sha256(domain_contract.model_dump(mode="json"))
    if contract_digest != contract_ref.descriptor_sha256:
        _fail(
            "domain_contract_digest_mismatch",
            descriptor_sha256=contract_digest,
            expected_descriptor_sha256=contract_ref.descriptor_sha256,
        )
    profile_ref = parent.semantic_profile_ref
    if (
        semantic_profile.profile_id != profile_ref.profile_id
        or semantic_profile.profile_revision != profile_ref.profile_revision
    ):
        _fail(
            "semantic_profile_identity_mismatch",
            profile_id=semantic_profile.profile_id,
            profile_revision=semantic_profile.profile_revision,
            expected_profile_id=profile_ref.profile_id,
            expected_profile_revision=profile_ref.profile_revision,
        )
    profile_digest = canonical_sha256(semantic_profile.model_dump(mode="json"))
    if profile_digest != profile_ref.descriptor_sha256:
        _fail(
            "semantic_profile_digest_mismatch",
            descriptor_sha256=profile_digest,
            expected_descriptor_sha256=profile_ref.descriptor_sha256,
        )


def _close_identity_decision_ids(
    contribution: KnowledgeContribution,
    dispositions: Sequence[ContributionDisposition],
) -> None:
    disposition_by_item = {item.item_id: item for item in dispositions}
    accepted_decision_ids = {
        item.decision.decision_id
        for item in contribution.items
        if isinstance(item, ProposeIdentityDecision)
        and disposition_by_item[item.item_id].disposition == "accepted"
    }
    for disposition in dispositions:
        for decision_id in disposition.identity_decision_ids:
            if decision_id not in accepted_decision_ids:
                _fail(
                    "identity_decision_id_unresolved",
                    item_id=disposition.item_id,
                    identity_decision_id=decision_id,
                )


def _validate_child_vocabulary(
    child: ParsedKnowledgeRevision,
    *,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2,
) -> None:
    for assertion in child.assertions_by_id.values():
        reason = domain_declaration_passes(
            assertion,
            domain_contract=domain_contract,
        )
        if reason is not None:
            _fail(
                "undeclared_domain_vocabulary",
                assertion_id=assertion.assertion_id,
                gate=reason,
            )
        reason = semantic_profile_passes(
            assertion,
            semantic_profile=semantic_profile,
        )
        if reason is not None:
            _fail(
                "undeclared_semantic_profile",
                assertion_id=assertion.assertion_id,
                gate=reason,
            )


def _apply_propose_entity(entities: dict[str, Entity], item: ProposeEntity) -> None:
    existing = entities.get(item.entity.entity_id)
    if existing is None:
        entities[item.entity.entity_id] = item.entity
        return
    if existing.model_dump(mode="json") != item.entity.model_dump(mode="json"):
        _fail("entity_id_collision", entity_id=item.entity.entity_id)


def _apply_propose_assertion(assertions: dict[str, Assertion], item: ProposeAssertion) -> None:
    existing = assertions.get(item.assertion.assertion_id)
    incoming = item.assertion
    if existing is None:
        assertions[incoming.assertion_id] = incoming
        return
    if existing.model_dump(mode="json") != incoming.model_dump(mode="json"):
        _fail("assertion_id_collision", assertion_id=incoming.assertion_id)


def _apply_retract(assertions: dict[str, Assertion], item: RetractAssertion) -> None:
    if item.target_assertion_id not in assertions:
        _fail("retract_missing_target", assertion_id=item.target_assertion_id)
    del assertions[item.target_assertion_id]


def _apply_supersede(assertions: dict[str, Assertion], item: SupersedeAssertion) -> None:
    if item.target_assertion_id not in assertions:
        _fail("supersede_missing_target", assertion_id=item.target_assertion_id)
    replacement = item.replacement_assertion
    colliding = assertions.get(replacement.assertion_id)
    if colliding is not None and replacement.assertion_id != item.target_assertion_id:
        _fail(
            "supersede_replacement_collision",
            assertion_id=replacement.assertion_id,
        )
    del assertions[item.target_assertion_id]
    assertions[replacement.assertion_id] = replacement


def _apply_identity(
    entities: dict[str, Entity],
    assertions: dict[str, Assertion],
    aliases: dict[str, IdentityAlias],
    item: ProposeIdentityDecision,
    space_id: str,
) -> None:
    decision = item.decision
    if decision.space_id != space_id:
        _fail(
            "identity_space_mismatch",
            decision_id=decision.decision_id,
            decision_space_id=decision.space_id,
            parent_space_id=space_id,
        )
    kind = decision.decision_kind
    if kind not in _MATERIALIZABLE_IDENTITY:
        _fail(
            "identity_kind_not_materializable_in_v5_1",
            decision_id=decision.decision_id,
            decision_kind=str(kind),
        )
    if kind is IdentityDecisionKind.REJECT_CANDIDATE:
        return
    if kind is IdentityDecisionKind.ALIAS_ADD:
        _apply_alias_add(entities, aliases, decision)
        return
    if kind is IdentityDecisionKind.ALIAS_REMOVE:
        _apply_alias_remove(aliases, decision)
        return
    _apply_merge(entities, assertions, aliases, decision)


def _apply_alias_add(
    entities: dict[str, Entity],
    aliases: dict[str, IdentityAlias],
    decision: IdentityDecisionV3,
) -> None:
    if len(decision.subject_entity_ids) != 1:
        _fail("alias_add_requires_one_subject", decision_id=decision.decision_id)
    entity_id = decision.subject_entity_ids[0]
    if entity_id not in entities:
        _fail("alias_add_missing_entity", entity_id=entity_id)
    alias = IdentityAlias(
        alias_id=decision.decision_id,
        entity_id=entity_id,
        alias_text=str(decision.alias),
        standing=KnowledgeStanding.ESTABLISHED,
    )
    existing = aliases.get(alias.alias_id)
    if existing is None:
        aliases[alias.alias_id] = alias
        return
    if existing.model_dump(mode="json") != alias.model_dump(mode="json"):
        _fail("alias_id_collision", alias_id=alias.alias_id)


def _apply_alias_remove(aliases: dict[str, IdentityAlias], decision: IdentityDecisionV3) -> None:
    subjects = set(decision.subject_entity_ids)
    alias_text = str(decision.alias)
    removed = [
        alias_id
        for alias_id, alias in aliases.items()
        if alias.entity_id in subjects and alias.alias_text == alias_text
    ]
    if not removed:
        _fail(
            "alias_remove_missing_target",
            alias_text=alias_text,
            subject_entity_ids=list(decision.subject_entity_ids),
        )
    for alias_id in removed:
        del aliases[alias_id]


def _apply_merge(
    entities: dict[str, Entity],
    assertions: dict[str, Assertion],
    aliases: dict[str, IdentityAlias],
    decision: IdentityDecisionV3,
) -> None:
    subjects = list(decision.subject_entity_ids)
    target = decision.target_entity_ids[0]
    for entity_id in (*subjects, target):
        if entity_id not in entities:
            _fail("merge_missing_entity", entity_id=entity_id)
    merged_away = {entity_id for entity_id in subjects if entity_id != target}

    rewritten: dict[str, Assertion] = {}
    for assertion_id, assertion in assertions.items():
        subject = (
            target if assertion.subject_entity_id in merged_away else assertion.subject_entity_id
        )
        value = assertion.value
        if isinstance(value, EntityRefValue) and value.entity_id in merged_away:
            value = EntityRefValue(entity_id=target)
        if subject != assertion.subject_entity_id or value != assertion.value:
            rewritten[assertion_id] = assertion.model_copy(
                update={"subject_entity_id": subject, "value": value}
            )
        else:
            rewritten[assertion_id] = assertion
    assertions.clear()
    assertions.update(rewritten)

    rewritten_aliases: dict[str, IdentityAlias] = {}
    for alias_id, alias in aliases.items():
        if alias.entity_id in merged_away:
            rewritten_aliases[alias_id] = alias.model_copy(update={"entity_id": target})
        else:
            rewritten_aliases[alias_id] = alias
    aliases.clear()
    aliases.update(rewritten_aliases)

    for entity_id in merged_away:
        del entities[entity_id]


def _rebuild_child(
    *,
    parent: ParsedKnowledgeRevision,
    publication: GovernedPublicationIdentity,
    payload: Mapping[str, Any],
    payload_sha: str,
) -> ParsedKnowledgeRevision:
    decoded = decode_native_graph_payload(payload)
    decoded = DecodedKnowledgeContent(
        entities=decoded.entities,
        assertions=decoded.assertions,
        aliases=decoded.aliases,
        evidence=decoded.evidence,
        graph_schema=parent.graph_schema,
        graph_payload_sha256=payload_sha,
    )
    revision = KnowledgeRevision(
        space_id=parent.space_id,
        revision_id=_CHILD_VALIDATION_REVISION_ID,
        parent_revision_id=parent.revision_id,
        created_at=publication.created_at,
        operation_ids=list(publication.operation_ids),
        graph_schema=parent.graph_schema,
        graph_payload_sha256=payload_sha,
        domain_contract_ref=_domain_contract_ref(parent),
        semantic_profile_ref=_semantic_profile_ref(parent),
        migration_origin_ref=_migration_origin_ref(parent),
    )
    return build_parsed_knowledge_revision(revision=revision, decoded_content=decoded)


def _domain_contract_ref(parent: ParsedKnowledgeRevision) -> DomainContractRef:
    ref = parent.domain_contract_ref
    return DomainContractRef(
        domain_id=ref.domain_id,
        domain_revision=ref.domain_revision,
        descriptor_sha256=ref.descriptor_sha256,
    )


def _semantic_profile_ref(parent: ParsedKnowledgeRevision) -> SemanticProfileRef:
    ref = parent.semantic_profile_ref
    return SemanticProfileRef(
        profile_id=ref.profile_id,
        profile_revision=ref.profile_revision,
        descriptor_sha256=ref.descriptor_sha256,
    )


def _migration_origin_ref(
    parent: ParsedKnowledgeRevision,
) -> MigrationOriginRef | None:
    origin = parent.migration_origin_ref
    if origin is None:
        return None
    return MigrationOriginRef(
        source_system=origin.source_system,
        source_root_id=origin.source_root_id,
        source_revision_id=origin.source_revision_id,
        source_payload_sha256=origin.source_payload_sha256,
        migration_manifest_sha256=origin.migration_manifest_sha256,
    )


def _entities_from_parsed(parent: ParsedKnowledgeRevision) -> list[Entity]:
    return [Entity(entity_id=entity.entity_id) for entity in parent.entities_by_id.values()]


def _assertions_from_parsed(parent: ParsedKnowledgeRevision) -> list[Assertion]:
    return [_assertion_from_parsed(item) for item in parent.assertions_by_id.values()]


def _assertion_from_parsed(assertion: ParsedAssertion) -> Assertion:
    value: EntityRefValue | LiteralValue | TermRefValue
    parsed_value = assertion.value
    if isinstance(parsed_value, ParsedEntityRefValue):
        value = EntityRefValue(entity_id=parsed_value.entity_id)
    elif isinstance(parsed_value, ParsedLiteralValue):
        value = LiteralValue(value=thaw_json_value(parsed_value.value))
    elif isinstance(parsed_value, ParsedTermRefValue):
        value = TermRefValue(term=parsed_value.term)
    else:
        _fail("unknown_assertion_value", assertion_id=assertion.assertion_id)

    vis = assertion.metadata.visibility
    if isinstance(vis, ParsedPublicVisibility):
        visibility: PublicVisibility | LabelsAnyVisibility | LabelsAllVisibility = (
            PublicVisibility()
        )
    elif isinstance(vis, ParsedLabelsAnyVisibility):
        visibility = LabelsAnyVisibility(labels=list(vis.labels))
    elif isinstance(vis, ParsedLabelsAllVisibility):
        visibility = LabelsAllVisibility(labels=list(vis.labels))
    else:
        _fail("unknown_visibility", assertion_id=assertion.assertion_id)

    temporal = assertion.metadata.temporal_scope
    if isinstance(temporal, ParsedUtcIntervalTemporalScope):
        temporal_scope: Any = UtcIntervalTemporalScope(
            valid_from=temporal.valid_from,
            valid_until=temporal.valid_until,
        )
    elif isinstance(temporal, ParsedDomainTemporalScope):
        temporal_scope = DomainTemporalScope.model_validate(
            {
                "schema": temporal.schema_term,
                "payload": thaw_json_value(temporal.payload),
            }
        )
    elif isinstance(temporal, ParsedUnknownTemporalScope):
        temporal_scope = UnknownTemporalScope()
    elif isinstance(temporal, ParsedTimelessTemporalScope):
        temporal_scope = TimelessTemporalScope()
    else:
        _fail("unknown_temporal_scope", assertion_id=assertion.assertion_id)

    standing = assertion.metadata.standing
    if not isinstance(standing, KnowledgeStanding):
        standing = KnowledgeStanding(str(standing))
    metadata = AssertionMetadata(
        scope=[
            ScopeBinding(axis=binding.axis, value=binding.value)
            for binding in assertion.metadata.scope
        ],
        visibility=visibility,
        epistemic_basis=EpistemicBasis(assertion.metadata.epistemic_basis),
        claim_mode=assertion.metadata.claim_mode,
        standing=standing,
        evidence_ref_ids=list(assertion.metadata.evidence_ref_ids),
        temporal_scope=temporal_scope,
        domain_metadata=[
            DomainMetadataEntry.model_validate(
                {
                    "schema": entry.schema_term,
                    "payload": thaw_json_value(entry.payload),
                }
            )
            for entry in assertion.metadata.domain_metadata
        ],
    )
    return Assertion(
        assertion_id=assertion.assertion_id,
        subject_entity_id=assertion.subject_entity_id,
        predicate=assertion.predicate,
        value=value,
        metadata=metadata,
    )


def _aliases_from_parsed(parent: ParsedKnowledgeRevision) -> list[IdentityAlias]:
    result: list[IdentityAlias] = []
    for alias in parent.aliases_by_id.values():
        standing = alias.standing
        if not isinstance(standing, KnowledgeStanding):
            standing = KnowledgeStanding(str(standing))
        result.append(
            IdentityAlias(
                alias_id=alias.alias_id,
                entity_id=alias.entity_id,
                alias_text=alias.alias_text,
                evidence_ref_ids=list(alias.evidence_ref_ids),
                standing=standing,
            )
        )
    return result


def _evidence_from_parsed(parent: ParsedKnowledgeRevision) -> list[EvidenceRefV3]:
    return [_evidence_ref_from_parsed(item) for item in parent.evidence_by_id.values()]


def _evidence_ref_from_parsed(evidence: ParsedEvidenceRef) -> EvidenceRefV3:
    return EvidenceRefV3.model_validate(
        {
            "evidence_ref_id": evidence.evidence_ref_id,
            "source_artifact_id": evidence.source_artifact_id,
            "source_revision_id": evidence.source_revision_id,
            "evidence_role": evidence.evidence_role,
            "can_open_source": evidence.can_open_source,
            "can_highlight_span": evidence.can_highlight_span,
            "locator": evidence.locator,
            "uri": evidence.uri,
            "source_locator": evidence.source_locator,
            "line_ref": evidence.line_ref,
            "source_span_ref_id": evidence.source_span_ref_id,
            "domain_metadata": [
                {
                    "schema": entry.schema_term,
                    "payload": thaw_json_value(entry.payload),
                }
                for entry in evidence.domain_metadata
            ],
        }
    )
