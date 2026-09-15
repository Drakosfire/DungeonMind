"""Pure builder for constructing ParsedKnowledgeRevision from decoded vNext primitives.

Enforces referential integrity, structural uniqueness, and deep immutability
without performing scope/visibility/domain admission or introducing domain/TTRPG concepts.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from dungeonmind.contracts.vnext.common import (
    DomainTemporalScope,
    LabelsAllVisibility,
    LabelsAnyVisibility,
    PublicVisibility,
    TimelessTemporalScope,
    UnknownTemporalScope,
    UtcIntervalTemporalScope,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    Entity,
    EntityRefValue,
    LiteralValue,
    TermRefValue,
)
from dungeonmind.contracts.vnext.knowledge import (
    IdentityAlias,
    KnowledgeRevision,
)
from dungeonmind.contracts.vnext.source import EvidenceRefV3

from .errors import RevisionStructuralIntegrityError
from .frozen_json import (
    FrozenDict,
    canonical_json_text,
    freeze_json_value,
)
from .model import (
    ParsedKnowledgeRevision,
    compute_compatibility_key,
    compute_semantic_digest,
)
from .records import (
    ParsedAssertion,
    ParsedAssertionMetadata,
    ParsedAssertionValue,
    ParsedDomainContractRef,
    ParsedDomainMetadataEntry,
    ParsedDomainTemporalScope,
    ParsedEntity,
    ParsedEntityRefValue,
    ParsedEvidenceRef,
    ParsedIdentityAlias,
    ParsedKnowledgeRevisionIdentity,
    ParsedLabelsAllVisibility,
    ParsedLabelsAnyVisibility,
    ParsedLiteralValue,
    ParsedMigrationOriginRef,
    ParsedPublicVisibility,
    ParsedScopeBinding,
    ParsedSemanticProfileRef,
    ParsedTemporalScope,
    ParsedTermRefValue,
    ParsedTimelessTemporalScope,
    ParsedUnknownTemporalScope,
    ParsedUtcIntervalTemporalScope,
    ParsedVisibility,
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class DecodedKnowledgeContent:
    """Optional container for already-decoded and verified vNext knowledge content."""

    entities: Sequence[Entity] = ()
    assertions: Sequence[Assertion] = ()
    aliases: Sequence[IdentityAlias] = ()
    evidence: Sequence[EvidenceRefV3] = ()
    graph_schema: str | None = None
    graph_payload_sha256: str | None = None


def build_parsed_knowledge_revision(
    revision: KnowledgeRevision,
    *,
    entities: Sequence[Entity] = (),
    assertions: Sequence[Assertion] = (),
    aliases: Sequence[IdentityAlias] = (),
    evidence: Sequence[EvidenceRefV3] = (),
    decoded_content: DecodedKnowledgeContent | None = None,
) -> ParsedKnowledgeRevision:
    """Build a deterministic, immutable ParsedKnowledgeRevision from decoded vNext primitives.

    Raises:
        RevisionStructuralIntegrityError: if duplicate IDs exist or referential integrity fails.
    """
    if decoded_content is not None:
        if (
            decoded_content.graph_schema is not None
            and decoded_content.graph_schema != revision.graph_schema
        ):
            raise RevisionStructuralIntegrityError(
                f"Decoded content graph_schema {decoded_content.graph_schema!r} "
                f"disagrees with revision graph_schema {revision.graph_schema!r}"
            )
        if (
            decoded_content.graph_payload_sha256 is not None
            and decoded_content.graph_payload_sha256 != revision.graph_payload_sha256
        ):
            raise RevisionStructuralIntegrityError(
                f"Decoded content graph_payload_sha256 {decoded_content.graph_payload_sha256!r} "
                f"disagrees with revision graph_payload_sha256 {revision.graph_payload_sha256!r}"
            )
        raw_entities = decoded_content.entities
        raw_assertions = decoded_content.assertions
        raw_aliases = decoded_content.aliases
        raw_evidence = decoded_content.evidence
    else:
        raw_entities = entities
        raw_assertions = assertions
        raw_aliases = aliases
        raw_evidence = evidence

    # --- 1. Entities ---
    entities_dict: dict[str, ParsedEntity] = {}
    for ent in raw_entities:
        eid = str(ent.entity_id)
        if eid in entities_dict:
            raise RevisionStructuralIntegrityError(f"Duplicate entity_id: {eid!r}")
        entities_dict[eid] = ParsedEntity(entity_id=eid)

    # --- 2. Evidence ---
    evidence_dict: dict[str, ParsedEvidenceRef] = {}
    for ev in raw_evidence:
        ev_id = str(ev.evidence_ref_id)
        if ev_id in evidence_dict:
            raise RevisionStructuralIntegrityError(f"Duplicate evidence_ref_id: {ev_id!r}")
        dm_entries = tuple(
            sorted(
                (
                    ParsedDomainMetadataEntry(
                        schema_term=str(dm.schema_term),
                        payload=freeze_json_value(dm.payload),
                    )
                    for dm in ev.domain_metadata
                ),
                key=lambda d: d.schema_term,
            )
        )
        evidence_dict[ev_id] = ParsedEvidenceRef(
            evidence_ref_id=ev_id,
            source_artifact_id=str(ev.source_artifact_id),
            source_revision_id=str(ev.source_revision_id) if ev.source_revision_id else None,
            evidence_role=str(ev.evidence_role),
            can_open_source=bool(ev.can_open_source),
            can_highlight_span=bool(ev.can_highlight_span),
            locator=str(ev.locator) if ev.locator else None,
            uri=str(ev.uri) if ev.uri else None,
            source_locator=str(ev.source_locator) if ev.source_locator else None,
            line_ref=str(ev.line_ref) if ev.line_ref else None,
            source_span_ref_id=str(ev.source_span_ref_id) if ev.source_span_ref_id else None,
            domain_metadata=dm_entries,
        )

    # --- 3. Aliases ---
    aliases_dict: dict[str, ParsedIdentityAlias] = {}
    for al in raw_aliases:
        al_id = str(al.alias_id)
        if al_id in aliases_dict:
            raise RevisionStructuralIntegrityError(f"Duplicate alias_id: {al_id!r}")
        target_eid = str(al.entity_id)
        if target_eid not in entities_dict:
            raise RevisionStructuralIntegrityError(
                f"Alias {al_id!r} references missing entity {target_eid!r}"
            )
        for ev_id in al.evidence_ref_ids:
            ev_str = str(ev_id)
            if ev_str not in evidence_dict:
                raise RevisionStructuralIntegrityError(
                    f"Alias {al_id!r} references missing evidence {ev_str!r}"
                )

        aliases_dict[al_id] = ParsedIdentityAlias(
            alias_id=al_id,
            entity_id=target_eid,
            alias_text=str(al.alias_text),
            evidence_ref_ids=tuple(sorted(str(eid) for eid in al.evidence_ref_ids)),
            standing=al.standing,
        )

    # --- 4. Assertions ---
    assertions_dict: dict[str, ParsedAssertion] = {}
    for a in raw_assertions:
        aid = str(a.assertion_id)
        if aid in assertions_dict:
            raise RevisionStructuralIntegrityError(f"Duplicate assertion_id: {aid!r}")

        subj_eid = str(a.subject_entity_id)
        if subj_eid not in entities_dict:
            raise RevisionStructuralIntegrityError(
                f"Assertion {aid!r} references missing subject entity {subj_eid!r}"
            )

        # Parse value
        val = a.value
        parsed_val: ParsedAssertionValue
        if isinstance(val, EntityRefValue):
            target_eid = str(val.entity_id)
            if target_eid not in entities_dict:
                raise RevisionStructuralIntegrityError(
                    f"Assertion {aid!r} references missing target entity {target_eid!r}"
                )
            parsed_val = ParsedEntityRefValue(entity_id=target_eid)
        elif isinstance(val, LiteralValue):
            frozen_val = freeze_json_value(val.value)
            canon_text = canonical_json_text(val.value)
            parsed_val = ParsedLiteralValue(value=frozen_val, canonical_json_text=canon_text)
        elif isinstance(val, TermRefValue):
            parsed_val = ParsedTermRefValue(term=str(val.term))
        else:
            raise RevisionStructuralIntegrityError(
                f"Assertion {aid!r} has unknown value kind: {val!r}"
            )

        # Parse metadata
        meta = a.metadata
        for ev_id in meta.evidence_ref_ids:
            ev_str = str(ev_id)
            if ev_str not in evidence_dict:
                raise RevisionStructuralIntegrityError(
                    f"Assertion {aid!r} references missing evidence {ev_str!r}"
                )

        parsed_scope = tuple(
            sorted(
                (ParsedScopeBinding(axis=str(sb.axis), value=str(sb.value)) for sb in meta.scope),
                key=lambda b: (b.axis, b.value),
            )
        )

        vis = meta.visibility
        parsed_vis: ParsedVisibility
        if isinstance(vis, LabelsAnyVisibility):
            sorted_labels = tuple(sorted(str(lbl) for lbl in vis.labels))
            parsed_vis = ParsedLabelsAnyVisibility(labels=sorted_labels)
        elif isinstance(vis, LabelsAllVisibility):
            sorted_labels = tuple(sorted(str(lbl) for lbl in vis.labels))
            parsed_vis = ParsedLabelsAllVisibility(labels=sorted_labels)
        elif isinstance(vis, PublicVisibility):
            parsed_vis = ParsedPublicVisibility()
        else:
            raise RevisionStructuralIntegrityError(
                f"Assertion {aid!r} has invalid or unknown visibility variant: {vis!r}"
            )

        temporal = meta.temporal_scope
        parsed_temporal: ParsedTemporalScope
        if isinstance(temporal, UtcIntervalTemporalScope):
            parsed_temporal = ParsedUtcIntervalTemporalScope(
                valid_from=temporal.valid_from,
                valid_until=temporal.valid_until,
            )
        elif isinstance(temporal, DomainTemporalScope):
            parsed_temporal = ParsedDomainTemporalScope(
                schema_term=str(temporal.schema_term),
                payload=freeze_json_value(temporal.payload),
            )
        elif isinstance(temporal, UnknownTemporalScope):
            parsed_temporal = ParsedUnknownTemporalScope()
        elif isinstance(temporal, TimelessTemporalScope):
            parsed_temporal = ParsedTimelessTemporalScope()
        else:
            raise RevisionStructuralIntegrityError(
                f"Assertion {aid!r} has invalid or unknown temporal scope variant: {temporal!r}"
            )

        dm_entries = tuple(
            sorted(
                (
                    ParsedDomainMetadataEntry(
                        schema_term=str(dm.schema_term),
                        payload=freeze_json_value(dm.payload),
                    )
                    for dm in meta.domain_metadata
                ),
                key=lambda d: d.schema_term,
            )
        )

        parsed_metadata = ParsedAssertionMetadata(
            scope=parsed_scope,
            visibility=parsed_vis,
            epistemic_basis=str(meta.epistemic_basis),
            claim_mode=str(meta.claim_mode),
            standing=meta.standing,
            evidence_ref_ids=tuple(sorted(str(eid) for eid in meta.evidence_ref_ids)),
            temporal_scope=parsed_temporal,
            domain_metadata=dm_entries,
        )

        assertions_dict[aid] = ParsedAssertion(
            assertion_id=aid,
            subject_entity_id=subj_eid,
            predicate=str(a.predicate),
            value=parsed_val,
            metadata=parsed_metadata,
        )

    # --- 5. Identity ---
    parent_rev_id = (
        str(revision.parent_revision_id) if revision.parent_revision_id else None
    )
    identity = ParsedKnowledgeRevisionIdentity(
        space_id=str(revision.space_id),
        revision_id=str(revision.revision_id),
        parent_revision_id=parent_rev_id,
        created_at=revision.created_at,
        operation_ids=tuple(str(op) for op in revision.operation_ids),
        graph_schema=str(revision.graph_schema),
        graph_payload_sha256=str(revision.graph_payload_sha256),
        domain_contract_ref=ParsedDomainContractRef(
            domain_id=str(revision.domain_contract_ref.domain_id),
            domain_revision=str(revision.domain_contract_ref.domain_revision),
            descriptor_sha256=str(revision.domain_contract_ref.descriptor_sha256),
        ),
        semantic_profile_ref=ParsedSemanticProfileRef(
            profile_id=str(revision.semantic_profile_ref.profile_id),
            profile_revision=str(revision.semantic_profile_ref.profile_revision),
            descriptor_sha256=str(revision.semantic_profile_ref.descriptor_sha256),
        ),
        migration_origin_ref=ParsedMigrationOriginRef(
            source_system=str(revision.migration_origin_ref.source_system),
            source_root_id=str(revision.migration_origin_ref.source_root_id),
            source_revision_id=str(revision.migration_origin_ref.source_revision_id),
            source_payload_sha256=str(revision.migration_origin_ref.source_payload_sha256),
            migration_manifest_sha256=str(revision.migration_origin_ref.migration_manifest_sha256),
        )
        if revision.migration_origin_ref
        else None,
    )

    return build_parsed_knowledge_revision_from_records(
        identity=identity,
        entities=entities_dict,
        assertions=assertions_dict,
        aliases=aliases_dict,
        evidence=evidence_dict,
    )


def build_parsed_knowledge_revision_from_records(
    identity: ParsedKnowledgeRevisionIdentity,
    *,
    entities: Mapping[str, ParsedEntity] | Sequence[ParsedEntity] = (),
    assertions: Mapping[str, ParsedAssertion] | Sequence[ParsedAssertion] = (),
    aliases: Mapping[str, ParsedIdentityAlias] | Sequence[ParsedIdentityAlias] = (),
    evidence: Mapping[str, ParsedEvidenceRef] | Sequence[ParsedEvidenceRef] = (),
) -> ParsedKnowledgeRevision:
    """Build a deterministic, immutable ParsedKnowledgeRevision from internal immutable records.

    Raises:
        RevisionStructuralIntegrityError: if duplicate IDs exist or referential integrity fails.
    """
    if isinstance(entities, Mapping):
        entities_dict = dict(entities)
        for key, ent in entities_dict.items():
            if key != ent.entity_id:
                raise RevisionStructuralIntegrityError(
                    f"Entity mapping key {key!r} does not match entity_id {ent.entity_id!r}"
                )
    else:
        entities_dict = {}
        for ent in entities:
            eid = ent.entity_id
            if eid in entities_dict:
                raise RevisionStructuralIntegrityError(f"Duplicate entity_id: {eid!r}")
            entities_dict[eid] = ent

    if isinstance(evidence, Mapping):
        evidence_dict = dict(evidence)
        for key, ev in evidence_dict.items():
            if key != ev.evidence_ref_id:
                raise RevisionStructuralIntegrityError(
                    "Evidence mapping key "
                    f"{key!r} does not match evidence_ref_id {ev.evidence_ref_id!r}"
                )
    else:
        evidence_dict = {}
        for ev in evidence:
            evid = ev.evidence_ref_id
            if evid in evidence_dict:
                raise RevisionStructuralIntegrityError(f"Duplicate evidence_ref_id: {evid!r}")
            evidence_dict[evid] = ev

    if isinstance(aliases, Mapping):
        aliases_dict = dict(aliases)
        for key, al in aliases_dict.items():
            if key != al.alias_id:
                raise RevisionStructuralIntegrityError(
                    f"Alias mapping key {key!r} does not match alias_id {al.alias_id!r}"
                )
    else:
        aliases_dict = {}
        for al in aliases:
            alid = al.alias_id
            if alid in aliases_dict:
                raise RevisionStructuralIntegrityError(f"Duplicate alias_id: {alid!r}")
            aliases_dict[alid] = al

    # Validate aliases referential integrity
    for al_id, al in aliases_dict.items():
        if al.entity_id not in entities_dict:
            raise RevisionStructuralIntegrityError(
                f"Alias {al_id!r} references missing entity {al.entity_id!r}"
            )
        for ev_id in al.evidence_ref_ids:
            if ev_id not in evidence_dict:
                raise RevisionStructuralIntegrityError(
                    f"Alias {al_id!r} references missing evidence {ev_id!r}"
                )

    if isinstance(assertions, Mapping):
        assertions_dict = dict(assertions)
        for key, asrt in assertions_dict.items():
            if key != asrt.assertion_id:
                raise RevisionStructuralIntegrityError(
                    "Assertion mapping key "
                    f"{key!r} does not match assertion_id {asrt.assertion_id!r}"
                )
    else:
        assertions_dict = {}
        for asrt in assertions:
            aid = asrt.assertion_id
            if aid in assertions_dict:
                raise RevisionStructuralIntegrityError(f"Duplicate assertion_id: {aid!r}")
            assertions_dict[aid] = asrt

    # Validate assertions referential integrity
    for aid, asrt in assertions_dict.items():
        if asrt.subject_entity_id not in entities_dict:
            raise RevisionStructuralIntegrityError(
                f"Assertion {aid!r} references missing subject entity {asrt.subject_entity_id!r}"
            )
        if (
            isinstance(asrt.value, ParsedEntityRefValue)
            and asrt.value.entity_id not in entities_dict
        ):
            raise RevisionStructuralIntegrityError(
                f"Assertion {aid!r} references missing target entity {asrt.value.entity_id!r}"
            )
        for ev_id in asrt.metadata.evidence_ref_ids:
            if ev_id not in evidence_dict:
                raise RevisionStructuralIntegrityError(
                    f"Assertion {aid!r} references missing evidence {ev_id!r}"
                )

    # --- Structural Indexes ---
    assertions_by_subject_builder: dict[str, list[str]] = {eid: [] for eid in entities_dict}
    entity_ref_outgoing_builder: dict[str, set[str]] = {eid: set() for eid in entities_dict}
    entity_ref_incoming_builder: dict[str, set[str]] = {eid: set() for eid in entities_dict}
    assertion_evidence_builder: dict[str, tuple[str, ...]] = {}
    evidence_supporters_builder: dict[str, list[str]] = {evid: [] for evid in evidence_dict}
    alias_exact_builder: dict[str, set[str]] = {}
    literal_exact_builder: dict[tuple[str, str], list[str]] = {}
    lexical_candidate_builder: dict[str, set[str]] = {}

    for aid in sorted(assertions_dict.keys()):
        asrt = assertions_dict[aid]
        assertions_by_subject_builder[asrt.subject_entity_id].append(aid)
        assertion_evidence_builder[aid] = asrt.metadata.evidence_ref_ids

        for evid in asrt.metadata.evidence_ref_ids:
            evidence_supporters_builder[evid].append(aid)

        if isinstance(asrt.value, ParsedEntityRefValue):
            entity_ref_outgoing_builder[asrt.subject_entity_id].add(asrt.value.entity_id)
            entity_ref_incoming_builder[asrt.value.entity_id].add(asrt.subject_entity_id)
        elif isinstance(asrt.value, ParsedLiteralValue):
            lit_key = (asrt.predicate, asrt.value.canonical_json_text)
            if lit_key not in literal_exact_builder:
                literal_exact_builder[lit_key] = []
            literal_exact_builder[lit_key].append(aid)

            # Lexical indexing for string values
            if isinstance(asrt.value.value, str):
                for tok in _TOKEN_PATTERN.findall(asrt.value.value.lower()):
                    if tok not in lexical_candidate_builder:
                        lexical_candidate_builder[tok] = set()
                    lexical_candidate_builder[tok].add(asrt.subject_entity_id)

    # Index aliases
    for al_id in sorted(aliases_dict.keys()):
        al = aliases_dict[al_id]
        norm_alias = al.alias_text.strip().casefold()
        if norm_alias not in alias_exact_builder:
            alias_exact_builder[norm_alias] = set()
        alias_exact_builder[norm_alias].add(al.entity_id)

        # Lexical indexing for alias tokens
        for tok in _TOKEN_PATTERN.findall(al.alias_text.lower()):
            if tok not in lexical_candidate_builder:
                lexical_candidate_builder[tok] = set()
            lexical_candidate_builder[tok].add(al.entity_id)

    # Finalize index structures with sorted tuples and wrap in FrozenDict
    assertions_by_subject = FrozenDict(
        {eid: tuple(sorted(aids)) for eid, aids in assertions_by_subject_builder.items()}
    )
    entity_ref_outgoing = FrozenDict(
        {eid: tuple(sorted(targets)) for eid, targets in entity_ref_outgoing_builder.items()}
    )
    entity_ref_incoming = FrozenDict(
        {eid: tuple(sorted(sources)) for eid, sources in entity_ref_incoming_builder.items()}
    )

    entity_adjacency = FrozenDict({
        eid: tuple(sorted(entity_ref_outgoing_builder[eid] | entity_ref_incoming_builder[eid]))
        for eid in entities_dict
    })

    assertion_evidence = FrozenDict(assertion_evidence_builder)
    evidence_supporters = FrozenDict(
        {evid: tuple(sorted(aids)) for evid, aids in evidence_supporters_builder.items()}
    )

    alias_exact_index = FrozenDict({
        norm_text: tuple(sorted(eids)) for norm_text, eids in alias_exact_builder.items()
    })
    literal_exact_index = FrozenDict({
        k: tuple(sorted(aids)) for k, aids in literal_exact_builder.items()
    })
    lexical_candidate_index = FrozenDict({
        tok: tuple(sorted(eids)) for tok, eids in lexical_candidate_builder.items()
    })

    semantic_digest = compute_semantic_digest(
        identity,
        entities_dict,
        assertions_dict,
        aliases_dict,
        evidence_dict,
    )
    compatibility_key = compute_compatibility_key(identity)

    return ParsedKnowledgeRevision(
        identity=identity,
        entities_by_id=FrozenDict(entities_dict),
        assertions_by_id=FrozenDict(assertions_dict),
        aliases_by_id=FrozenDict(aliases_dict),
        evidence_by_id=FrozenDict(evidence_dict),
        assertions_by_subject=assertions_by_subject,
        entity_ref_outgoing=entity_ref_outgoing,
        entity_ref_incoming=entity_ref_incoming,
        entity_adjacency=entity_adjacency,
        assertion_evidence=assertion_evidence,
        evidence_supporters=evidence_supporters,
        alias_exact_index=alias_exact_index,
        literal_exact_index=literal_exact_index,
        lexical_candidate_index=lexical_candidate_index,
        semantic_digest=semantic_digest,
        compatibility_key=compatibility_key,
    )
