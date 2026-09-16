"""Focused unit tests for vNext ParsedKnowledgeRevision and structural indexes.

Covers the complete 40-item acceptance matrix from HANDOFF-v1-1-parsed-knowledge-revision-core.md.
"""

from __future__ import annotations

import copy
import json
import random
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dungeonmind.application.vnext import (
    PARSED_REVISION_FORMAT_VERSION,
    ParsedDomainContractRef,
    ParsedDomainTemporalScope,
    ParsedEntity,
    ParsedKnowledgeRevision,
    ParsedLiteralValue,
    ParsedScopeBinding,
    ParsedSemanticProfileRef,
    RevisionStructuralIntegrityError,
    build_parsed_knowledge_revision,
    compute_compatibility_key,
    thaw_json_value,
)
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
    UtcIntervalTemporalScope,
    canonical_json,
    sha256,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractRef,
    Entity,
    EntityRefValue,
    LiteralValue,
    TermRefValue,
)
from dungeonmind.contracts.vnext.knowledge import (
    IdentityAlias,
    KnowledgeRevision,
    MigrationOriginRef,
)
from dungeonmind.contracts.vnext.source import EvidenceRefV3

CANONICAL_V0_AGGREGATE = "fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "vnext"
CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "Docs" / "Contracts" / "vnext"
BENCHMARKS_DIR = Path(__file__).resolve().parents[2] / "Docs" / "Benchmarks"


def _make_base_revision() -> KnowledgeRevision:
    return KnowledgeRevision(
        space_id="space:test-space",
        revision_id="rev:test-0001",
        parent_revision_id="rev:test-0000",
        created_at=datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC),
        operation_ids=["op:test-1", "op:test-2"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="a" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id="test.domain",
            domain_revision="1",
            descriptor_sha256="b" * 64,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id="test.profile",
            profile_revision="1",
            descriptor_sha256="c" * 64,
        ),
        migration_origin_ref=MigrationOriginRef(
            source_system="origin_system",
            source_root_id="root_01",
            source_revision_id="rev_01",
            source_payload_sha256="d" * 64,
            migration_manifest_sha256="e" * 64,
        ),
    )


def _make_sample_entities() -> list[Entity]:
    return [
        Entity(entity_id="ent:alice"),
        Entity(entity_id="ent:bob"),
        Entity(entity_id="ent:charlie"),
        Entity(entity_id="ent:project-alpha"),
    ]


def _make_sample_evidence() -> list[EvidenceRefV3]:
    return [
        EvidenceRefV3(
            evidence_ref_id="ev:doc-1",
            source_artifact_id="art:handbook",
            source_revision_id="srcrev:1",
            evidence_role="support",
            can_open_source=True,
            can_highlight_span=True,
            locator="§1",
            uri="https://corp.internal/handbook.md",
            source_locator=None,
            line_ref="L10-L20",
            source_span_ref_id=None,
            domain_metadata=[
                DomainMetadataEntry(schema="corp:confidence", payload={"score": 0.95})
            ],
        ),
        EvidenceRefV3(
            evidence_ref_id="ev:doc-2",
            source_artifact_id="art:memo",
            source_revision_id="srcrev:2",
            evidence_role="context",
            can_open_source=False,
            can_highlight_span=False,
            locator="p2",
            uri=None,
            source_locator=None,
            line_ref=None,
            source_span_ref_id=None,
            domain_metadata=[],
        ),
    ]


def _make_sample_aliases() -> list[IdentityAlias]:
    return [
        IdentityAlias(
            alias_id="al:alice-alias",
            entity_id="ent:alice",
            alias_text="The Architect",
            evidence_ref_ids=["ev:doc-1"],
            standing=KnowledgeStanding.ESTABLISHED,
        ),
        IdentityAlias(
            alias_id="al:charlie-alias-ambiguous",
            entity_id="ent:charlie",
            alias_text="The Architect",
            evidence_ref_ids=["ev:doc-2"],
            standing=KnowledgeStanding.PROVISIONAL,
        ),
    ]


def _make_sample_assertions() -> list[Assertion]:
    return [
        Assertion(
            assertion_id="asrt:alice-owns-alpha",
            subject_entity_id="ent:alice",
            predicate="corp:owns",
            value=EntityRefValue(entity_id="ent:project-alpha"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="corp:dept", value="core-eng")],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="corp:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=["ev:doc-1"],
                temporal_scope=UtcIntervalTemporalScope(
                    valid_from=datetime(2026, 1, 1, tzinfo=UTC),
                    valid_until=None,
                ),
                domain_metadata=[
                    DomainMetadataEntry(schema="corp:review", payload={"approved": True})
                ],
            ),
        ),
        Assertion(
            assertion_id="asrt:bob-owns-alpha-provisional",
            subject_entity_id="ent:bob",
            predicate="corp:owns",
            value=EntityRefValue(entity_id="ent:project-alpha"),
            metadata=AssertionMetadata(
                scope=[ScopeBinding(axis="corp:dept", value="core-eng")],
                visibility=LabelsAnyVisibility(labels=["role:lead"]),
                epistemic_basis=EpistemicBasis.INFERRED,
                claim_mode="corp:belief",
                standing=KnowledgeStanding.PROVISIONAL,
                evidence_ref_ids=["ev:doc-2"],
                temporal_scope=TimelessTemporalScope(),
                domain_metadata=[],
            ),
        ),
        Assertion(
            assertion_id="asrt:charlie-title",
            subject_entity_id="ent:charlie",
            predicate="corp:title",
            value=LiteralValue(value={"title": "Principal Architect", "level": 7}),
            metadata=AssertionMetadata(
                scope=[],
                visibility=LabelsAllVisibility(labels=["role:hr", "role:leadership"]),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="corp:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=["ev:doc-1", "ev:doc-2"],
                temporal_scope=DomainTemporalScope(
                    schema="corp:fictional_quarter",
                    payload={"quarter": "2026Q3"},
                ),
                domain_metadata=[],
            ),
        ),
        Assertion(
            assertion_id="asrt:alice-title-duplicate-literal",
            subject_entity_id="ent:alice",
            predicate="corp:title",
            value=LiteralValue(value={"title": "Principal Architect", "level": 7}),
            metadata=AssertionMetadata(
                scope=[],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="corp:fact",
                standing=KnowledgeStanding.ESTABLISHED,
                evidence_ref_ids=["ev:doc-1"],
                temporal_scope=TimelessTemporalScope(),
                domain_metadata=[],
            ),
        ),
        Assertion(
            assertion_id="asrt:charlie-retracted",
            subject_entity_id="ent:charlie",
            predicate="corp:status",
            value=TermRefValue(term="corp:on_leave"),
            metadata=AssertionMetadata(
                scope=[],
                visibility=PublicVisibility(),
                epistemic_basis=EpistemicBasis.ASSERTED,
                claim_mode="corp:fact",
                standing=KnowledgeStanding.RETRACTED,
                evidence_ref_ids=["ev:doc-2"],
                temporal_scope=TimelessTemporalScope(),
                domain_metadata=[],
            ),
        ),
    ]


def _build_standard_parsed() -> ParsedKnowledgeRevision:
    return build_parsed_knowledge_revision(
        revision=_make_base_revision(),
        entities=_make_sample_entities(),
        assertions=_make_sample_assertions(),
        aliases=_make_sample_aliases(),
        evidence=_make_sample_evidence(),
    )


# --- Matrix Tests 1..40 ---

def test_01_exact_revision_identity_preserved() -> None:
    rev = _make_base_revision()
    # Explicitly test with unsorted operation_ids to prove sequence preservation
    rev.operation_ids = ["op:zulu", "op:alpha", "op:bravo"]
    parsed = build_parsed_knowledge_revision(revision=rev)
    assert parsed.space_id == "space:test-space"
    assert parsed.revision_id == "rev:test-0001"
    assert parsed.parent_revision_id == "rev:test-0000"
    assert parsed.created_at == rev.created_at
    assert parsed.operation_ids == ("op:zulu", "op:alpha", "op:bravo")
    assert parsed.graph_schema == "dm_vnext_graph_v1"
    assert parsed.graph_payload_sha256 == "a" * 64
    assert parsed.format_version == PARSED_REVISION_FORMAT_VERSION


def test_02_exact_domain_contract_ref_preserved() -> None:
    parsed = _build_standard_parsed()
    dref = parsed.domain_contract_ref
    assert dref.domain_id == "test.domain"
    assert dref.domain_revision == "1"
    assert dref.descriptor_sha256 == "b" * 64


def test_03_exact_semantic_profile_ref_preserved() -> None:
    parsed = _build_standard_parsed()
    pref = parsed.semantic_profile_ref
    assert pref.profile_id == "test.profile"
    assert pref.profile_revision == "1"
    assert pref.descriptor_sha256 == "c" * 64


def test_04_entities_retrievable_by_exact_id() -> None:
    parsed = _build_standard_parsed()
    ent = parsed.get_entity("ent:alice")
    assert ent is not None
    assert ent.entity_id == "ent:alice"
    assert parsed.get_entity("ent:nonexistent") is None


def test_05_assertions_retrievable_by_exact_id() -> None:
    parsed = _build_standard_parsed()
    asrt = parsed.get_assertion("asrt:alice-owns-alpha")
    assert asrt is not None
    assert asrt.subject_entity_id == "ent:alice"
    assert asrt.predicate == "corp:owns"
    assert parsed.get_assertion("asrt:missing") is None


def test_06_aliases_retrievable_by_exact_id() -> None:
    parsed = _build_standard_parsed()
    al = parsed.get_alias("al:alice-alias")
    assert al is not None
    assert al.entity_id == "ent:alice"
    assert al.alias_text == "The Architect"
    assert parsed.get_alias("al:missing") is None


def test_07_evidence_refs_retrievable_by_exact_id() -> None:
    parsed = _build_standard_parsed()
    ev = parsed.get_evidence("ev:doc-1")
    assert ev is not None
    assert ev.source_artifact_id == "art:handbook"
    assert ev.can_open_source is True
    assert parsed.get_evidence("ev:missing") is None


def test_08_subject_assertions_index_complete_and_deterministic() -> None:
    parsed = _build_standard_parsed()
    alice_asrts = parsed.get_subject_assertions("ent:alice")
    alice_ids = tuple(a.assertion_id for a in alice_asrts)
    assert alice_ids == ("asrt:alice-owns-alpha", "asrt:alice-title-duplicate-literal")
    assert parsed.get_subject_assertions("ent:project-alpha") == ()


def test_09_incoming_adjacency_complete_and_deterministic() -> None:
    parsed = _build_standard_parsed()
    incoming = parsed.entity_ref_incoming["ent:project-alpha"]
    assert incoming == ("ent:alice", "ent:bob")
    assert parsed.entity_ref_incoming["ent:alice"] == ()
    assert parsed.get_incoming_entity_ref_assertion_ids("ent:project-alpha") == (
        "asrt:alice-owns-alpha",
        "asrt:bob-owns-alpha-provisional",
    )
    assert parsed.get_incoming_entity_ref_assertion_ids("ent:alice") == ()


def test_10_outgoing_adjacency_complete_and_deterministic() -> None:
    parsed = _build_standard_parsed()
    outgoing = parsed.entity_ref_outgoing["ent:alice"]
    assert outgoing == ("ent:project-alpha",)
    assert parsed.entity_ref_outgoing["ent:project-alpha"] == ()
    assert parsed.get_outgoing_entity_ref_assertion_ids("ent:alice") == (
        "asrt:alice-owns-alpha",
    )
    assert parsed.get_outgoing_entity_ref_assertion_ids("ent:project-alpha") == ()


def test_11_touching_adjacency_indexed_without_full_scan() -> None:
    parsed = _build_standard_parsed()
    adj = parsed.get_adjacent_entities("ent:project-alpha")
    assert adj == ("ent:alice", "ent:bob")
    assert parsed.get_adjacent_entities("ent:alice") == ("ent:project-alpha",)


def test_12_assertion_evidence_index_exact() -> None:
    parsed = _build_standard_parsed()
    assert parsed.assertion_evidence["asrt:alice-owns-alpha"] == ("ev:doc-1",)
    assert parsed.assertion_evidence["asrt:charlie-title"] == ("ev:doc-1", "ev:doc-2")


def test_13_evidence_supporters_index_exact() -> None:
    parsed = _build_standard_parsed()
    doc1_supporters = parsed.get_evidence_supporters("ev:doc-1")
    doc1_ids = tuple(a.assertion_id for a in doc1_supporters)
    assert doc1_ids == (
        "asrt:alice-owns-alpha",
        "asrt:alice-title-duplicate-literal",
        "asrt:charlie-title",
    )


def test_14_alias_exact_index_preserves_ambiguity() -> None:
    parsed = _build_standard_parsed()
    matched = parsed.lookup_alias("The Architect")
    assert matched == ("ent:alice", "ent:charlie")
    assert parsed.lookup_alias("the architect") == ("ent:alice", "ent:charlie")
    assert parsed.lookup_alias("  THE ARCHITECT  ") == ("ent:alice", "ent:charlie")


def test_15_literal_exact_index_preserves_multiple_matching_assertions() -> None:
    parsed = _build_standard_parsed()
    canonical_val = json.dumps(
        {"level": 7, "title": "Principal Architect"},
        separators=(",", ":"),
        sort_keys=True,
    )
    matched = parsed.lookup_literal("corp:title", canonical_val)
    assert matched == ("asrt:alice-title-duplicate-literal", "asrt:charlie-title")


def test_16_lexical_candidate_index_deterministic_and_non_authoritative() -> None:
    parsed = _build_standard_parsed()
    candidates = parsed.lookup_lexical_candidates("architect")
    assert set(candidates) == {"ent:alice", "ent:charlie"}


def test_17_duplicate_entity_id_fails_closed() -> None:
    rev = _make_base_revision()
    entities = [Entity(entity_id="ent:dup"), Entity(entity_id="ent:dup")]
    with pytest.raises(RevisionStructuralIntegrityError, match="Duplicate entity_id"):
        build_parsed_knowledge_revision(revision=rev, entities=entities)


def test_18_duplicate_assertion_id_fails_closed() -> None:
    rev = _make_base_revision()
    entities = [Entity(entity_id="ent:x")]
    a1 = Assertion(
        assertion_id="asrt:dup",
        subject_entity_id="ent:x",
        predicate="corp:p",
        value=LiteralValue(value="v1"),
        metadata=AssertionMetadata(
            scope=[],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="corp:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=[],
            temporal_scope=TimelessTemporalScope(),
            domain_metadata=[],
        ),
    )
    a2 = copy.deepcopy(a1)
    with pytest.raises(RevisionStructuralIntegrityError, match="Duplicate assertion_id"):
        build_parsed_knowledge_revision(revision=rev, entities=entities, assertions=[a1, a2])


def test_19_duplicate_alias_id_fails_closed() -> None:
    rev = _make_base_revision()
    entities = [Entity(entity_id="ent:x")]
    al1 = IdentityAlias(
        alias_id="al:dup",
        entity_id="ent:x",
        alias_text="Alias 1",
        evidence_ref_ids=[],
        standing=KnowledgeStanding.ESTABLISHED,
    )
    al2 = copy.deepcopy(al1)
    with pytest.raises(RevisionStructuralIntegrityError, match="Duplicate alias_id"):
        build_parsed_knowledge_revision(revision=rev, entities=entities, aliases=[al1, al2])


def test_20_duplicate_evidence_id_fails_closed() -> None:
    rev = _make_base_revision()
    ev1 = EvidenceRefV3(
        evidence_ref_id="ev:dup",
        source_artifact_id="art:1",
        evidence_role="support",
        can_open_source=True,
        can_highlight_span=False,
    )
    ev2 = copy.deepcopy(ev1)
    with pytest.raises(RevisionStructuralIntegrityError, match="Duplicate evidence_ref_id"):
        build_parsed_knowledge_revision(revision=rev, evidence=[ev1, ev2])


def test_21_missing_assertion_subject_fails_closed() -> None:
    rev = _make_base_revision()
    entities = [Entity(entity_id="ent:exists")]
    a = Assertion(
        assertion_id="asrt:1",
        subject_entity_id="ent:missing_subject",
        predicate="corp:p",
        value=LiteralValue(value="v"),
        metadata=AssertionMetadata(
            scope=[],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="corp:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=[],
            temporal_scope=TimelessTemporalScope(),
            domain_metadata=[],
        ),
    )
    with pytest.raises(RevisionStructuralIntegrityError, match="references missing subject entity"):
        build_parsed_knowledge_revision(revision=rev, entities=entities, assertions=[a])


def test_22_missing_entity_ref_target_fails_closed() -> None:
    rev = _make_base_revision()
    entities = [Entity(entity_id="ent:exists")]
    a = Assertion(
        assertion_id="asrt:1",
        subject_entity_id="ent:exists",
        predicate="corp:rel",
        value=EntityRefValue(entity_id="ent:missing_target"),
        metadata=AssertionMetadata(
            scope=[],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="corp:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=[],
            temporal_scope=TimelessTemporalScope(),
            domain_metadata=[],
        ),
    )
    with pytest.raises(RevisionStructuralIntegrityError, match="references missing target entity"):
        build_parsed_knowledge_revision(revision=rev, entities=entities, assertions=[a])


def test_23_missing_assertion_evidence_fails_closed() -> None:
    rev = _make_base_revision()
    entities = [Entity(entity_id="ent:exists")]
    a = Assertion(
        assertion_id="asrt:1",
        subject_entity_id="ent:exists",
        predicate="corp:p",
        value=LiteralValue(value="v"),
        metadata=AssertionMetadata(
            scope=[],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="corp:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=["ev:missing_evidence"],
            temporal_scope=TimelessTemporalScope(),
            domain_metadata=[],
        ),
    )
    with pytest.raises(RevisionStructuralIntegrityError, match="references missing evidence"):
        build_parsed_knowledge_revision(revision=rev, entities=entities, assertions=[a])


def test_24_missing_alias_entity_fails_closed() -> None:
    rev = _make_base_revision()
    al = IdentityAlias(
        alias_id="al:1",
        entity_id="ent:missing_entity",
        alias_text="Ghost",
        evidence_ref_ids=[],
        standing=KnowledgeStanding.ESTABLISHED,
    )
    with pytest.raises(RevisionStructuralIntegrityError, match="references missing entity"):
        build_parsed_knowledge_revision(revision=rev, aliases=[al])


def test_25_missing_alias_evidence_fails_closed() -> None:
    rev = _make_base_revision()
    entities = [Entity(entity_id="ent:exists")]
    al = IdentityAlias(
        alias_id="al:1",
        entity_id="ent:exists",
        alias_text="Real",
        evidence_ref_ids=["ev:missing_ev"],
        standing=KnowledgeStanding.ESTABLISHED,
    )
    with pytest.raises(RevisionStructuralIntegrityError, match="references missing evidence"):
        build_parsed_knowledge_revision(revision=rev, entities=entities, aliases=[al])


def test_26_all_assertion_standings_represented() -> None:
    parsed = _build_standard_parsed()
    standings = {a.metadata.standing for a in parsed.assertions_by_id.values()}
    assert KnowledgeStanding.ESTABLISHED in standings
    assert KnowledgeStanding.PROVISIONAL in standings
    assert KnowledgeStanding.RETRACTED in standings
    assert parsed.get_assertion("asrt:charlie-retracted") is not None


def test_27_scope_and_visibility_preserved_not_applied() -> None:
    parsed = _build_standard_parsed()
    # Scoped and private assertions must still exist in parsed revision
    asrt = parsed.get_assertion("asrt:bob-owns-alpha-provisional")
    assert asrt is not None
    assert asrt.metadata.visibility.kind == "labels_any"
    assert asrt.metadata.scope == (ParsedScopeBinding(axis="corp:dept", value="core-eng"),)


def test_28_arbitrary_literal_json_round_trips() -> None:
    parsed = _build_standard_parsed()
    asrt = parsed.get_assertion("asrt:charlie-title")
    assert asrt is not None
    assert isinstance(asrt.value, ParsedLiteralValue)
    thawed = thaw_json_value(asrt.value.value)
    assert thawed == {"title": "Principal Architect", "level": 7}


def test_29_arbitrary_domain_metadata_json_round_trips() -> None:
    parsed = _build_standard_parsed()
    asrt = parsed.get_assertion("asrt:alice-owns-alpha")
    assert asrt is not None
    dm = asrt.metadata.domain_metadata[0]
    assert dm.schema_term == "corp:review"
    assert thaw_json_value(dm.payload) == {"approved": True}


def test_30_arbitrary_domain_temporal_json_round_trips() -> None:
    parsed = _build_standard_parsed()
    asrt = parsed.get_assertion("asrt:charlie-title")
    assert asrt is not None
    assert asrt.metadata.temporal_scope.kind == "domain_ref"
    assert asrt.metadata.temporal_scope.schema_term == "corp:fictional_quarter"
    assert thaw_json_value(asrt.metadata.temporal_scope.payload) == {"quarter": "2026Q3"}


def test_31_mutation_of_original_pydantic_input_cannot_change_parsed_model() -> None:
    rev = _make_base_revision()
    entities = _make_sample_entities()
    assertions = _make_sample_assertions()
    parsed = build_parsed_knowledge_revision(
        revision=rev,
        entities=entities,
        assertions=assertions,
        aliases=_make_sample_aliases(),
        evidence=_make_sample_evidence(),
    )
    digest_before = parsed.semantic_digest

    # Mutate original pydantic list
    entities.append(Entity(entity_id="ent:injected"))
    assertions[0].predicate = "corp:mutated"

    assert "ent:injected" not in parsed.entities_by_id
    asrt = parsed.get_assertion("asrt:alice-owns-alpha")
    assert asrt is not None
    assert asrt.predicate == "corp:owns"
    assert parsed.semantic_digest == digest_before


def test_32_mutation_of_original_nested_json_cannot_change_parsed_model() -> None:
    rev = _make_base_revision()
    nested_payload = {"config": {"threshold": 42, "tags": ["a", "b"]}}
    a = Assertion(
        assertion_id="asrt:nested",
        subject_entity_id="ent:alice",
        predicate="corp:config",
        value=LiteralValue(value=nested_payload),
        metadata=AssertionMetadata(
            scope=[],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="corp:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=[],
            temporal_scope=TimelessTemporalScope(),
            domain_metadata=[],
        ),
    )
    parsed = build_parsed_knowledge_revision(
        revision=rev,
        entities=[Entity(entity_id="ent:alice")],
        assertions=[a],
    )
    digest_before = parsed.semantic_digest

    # Mutate the caller's dictionary
    nested_payload["config"]["threshold"] = 9999
    nested_payload["config"]["tags"].append("POISON")

    parsed_asrt = parsed.get_assertion("asrt:nested")
    assert parsed_asrt is not None
    assert isinstance(parsed_asrt.value, ParsedLiteralValue)
    thawed = thaw_json_value(parsed_asrt.value.value)
    assert thawed["config"]["threshold"] == 42
    assert thawed["config"]["tags"] == ["a", "b"]
    assert parsed.semantic_digest == digest_before


def test_33_exposed_parsed_mappings_cannot_be_mutated() -> None:
    parsed = _build_standard_parsed()

    # Mapping interface mutation attempts
    with pytest.raises(TypeError):
        parsed.entities_by_id["ent:new"] = ParsedEntity(entity_id="ent:new")  # type: ignore

    with pytest.raises(TypeError):
        del parsed.assertions_by_id["asrt:alice-owns-alpha"]  # type: ignore

    with pytest.raises(AttributeError):
        parsed.entities_by_id.pop("ent:alice")  # type: ignore

    with pytest.raises(AttributeError):
        parsed.entities_by_id.clear()  # type: ignore

    # Backing-state escape / direct poison attempt regression
    assert not hasattr(parsed.entities_by_id, "_data")
    with pytest.raises(AttributeError):
        _ = parsed.entities_by_id._data  # type: ignore

    proxy = parsed.entities_by_id._proxy  # type: ignore
    with pytest.raises(TypeError):
        proxy["ent:poison"] = ParsedEntity(entity_id="ent:poison")

    with pytest.raises(AttributeError):
        proxy.clear()

    with pytest.raises(AttributeError):
        proxy.pop("ent:alice")

    with pytest.raises(AttributeError):
        proxy.update({})

    # Attribute immutability on FrozenDict itself
    with pytest.raises(TypeError):
        parsed.entities_by_id._proxy = None  # type: ignore

    with pytest.raises(TypeError):
        parsed.entities_by_id._items = ()  # type: ignore

    with pytest.raises(TypeError):
        parsed.entities_by_id._hash = 0  # type: ignore

    with pytest.raises(TypeError):
        parsed.entities_by_id.new_attr = "poison"  # type: ignore

    with pytest.raises(TypeError):
        del parsed.entities_by_id._proxy  # type: ignore

    with pytest.raises(TypeError):
        del parsed.entities_by_id._hash  # type: ignore

    # Hash consistency and resistance to stale hash poisoning
    cached_hash = hash(parsed.entities_by_id)
    assert hash(parsed.entities_by_id) == cached_hash


def test_34_reordered_input_builds_same_semantic_digest() -> None:
    rev = _make_base_revision()
    ents = _make_sample_entities()
    asrts = _make_sample_assertions()
    aliases = _make_sample_aliases()
    evs = _make_sample_evidence()

    p_ordered = build_parsed_knowledge_revision(
        revision=rev, entities=ents, assertions=asrts, aliases=aliases, evidence=evs
    )

    # Reverse order
    p_reversed = build_parsed_knowledge_revision(
        revision=rev,
        entities=list(reversed(ents)),
        assertions=list(reversed(asrts)),
        aliases=list(reversed(aliases)),
        evidence=list(reversed(evs)),
    )

    # Shuffled order with fixed seed
    rng = random.Random(1337)
    shuffled_ents = list(ents)
    shuffled_asrts = list(asrts)
    shuffled_aliases = list(aliases)
    shuffled_evs = list(evs)
    rng.shuffle(shuffled_ents)
    rng.shuffle(shuffled_asrts)
    rng.shuffle(shuffled_aliases)
    rng.shuffle(shuffled_evs)

    p_shuffled = build_parsed_knowledge_revision(
        revision=rev,
        entities=shuffled_ents,
        assertions=shuffled_asrts,
        aliases=shuffled_aliases,
        evidence=shuffled_evs,
    )

    assert p_ordered.semantic_digest == p_reversed.semantic_digest
    assert p_ordered.semantic_digest == p_shuffled.semantic_digest


def test_35_reordered_input_builds_same_index_order() -> None:
    rev = _make_base_revision()
    ents = _make_sample_entities()
    asrts = _make_sample_assertions()
    aliases = _make_sample_aliases()
    evs = _make_sample_evidence()

    p1 = build_parsed_knowledge_revision(
        revision=rev, entities=ents, assertions=asrts, aliases=aliases, evidence=evs
    )
    p2 = build_parsed_knowledge_revision(
        revision=rev,
        entities=list(reversed(ents)),
        assertions=list(reversed(asrts)),
        aliases=list(reversed(aliases)),
        evidence=list(reversed(evs)),
    )

    assert dict(p1.assertions_by_subject) == dict(p2.assertions_by_subject)
    assert dict(p1.entity_ref_outgoing) == dict(p2.entity_ref_outgoing)
    assert dict(p1.entity_ref_incoming) == dict(p2.entity_ref_incoming)
    assert dict(p1.entity_ref_outgoing_assertions) == dict(p2.entity_ref_outgoing_assertions)
    assert dict(p1.entity_ref_incoming_assertions) == dict(p2.entity_ref_incoming_assertions)
    assert dict(p1.entity_adjacency) == dict(p2.entity_adjacency)
    assert dict(p1.assertion_evidence) == dict(p2.assertion_evidence)
    assert dict(p1.evidence_supporters) == dict(p2.evidence_supporters)
    assert dict(p1.alias_exact_index) == dict(p2.alias_exact_index)
    assert dict(p1.literal_exact_index) == dict(p2.literal_exact_index)
    assert dict(p1.lexical_candidate_index) == dict(p2.lexical_candidate_index)


def test_36_generic_organizational_memory_fixture_builds_without_ttrpg_imports() -> None:
    path = FIXTURES_DIR / "organizational_memory_v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    entities = [Entity.model_validate(e) for e in data["entities"]]
    assertions = [Assertion.model_validate(a) for a in data["assertions"]]
    evidence = [EvidenceRefV3.model_validate(ev) for ev in data["sources"]["evidence"]]

    rev = KnowledgeRevision(
        space_id=data["space_id"],
        revision_id="rev:org-memory-v1",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:org-load"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="0" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id=data["domain_contract"]["domain_id"],
            domain_revision=data["domain_contract"]["domain_revision"],
            descriptor_sha256="1" * 64,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id="organization.profile",
            profile_revision="1",
            descriptor_sha256="2" * 64,
        ),
    )

    parsed = build_parsed_knowledge_revision(
        revision=rev,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )
    assert len(parsed.entities_by_id) == 5
    assert len(parsed.assertions_by_id) == 7
    assert len(parsed.evidence_by_id) == 2
    # Verify unscoped charter assertion is represented
    unscoped = parsed.get_assertion("asrt:org-charter-unscoped")
    assert unscoped is not None
    assert unscoped.metadata.scope == ()


def test_37_adversarial_epistemic_identity_fixture_builds_without_collapsing_conflicts() -> None:
    path = FIXTURES_DIR / "adversarial_epistemic_identity_v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    entities = [Entity.model_validate(e) for e in data["entities"]]
    assertions = [Assertion.model_validate(a) for a in data["assertions"]]
    evidence = [EvidenceRefV3.model_validate(ev) for ev in data["evidence"]]

    rev = KnowledgeRevision(
        space_id=data["space_id"],
        revision_id="rev:adversarial-v1",
        created_at=datetime(2026, 9, 15, tzinfo=UTC),
        operation_ids=["op:adv-load"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256="0" * 64,
        domain_contract_ref=DomainContractRef(
            domain_id="adv.domain",
            domain_revision="1",
            descriptor_sha256="1" * 64,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id="adv.profile",
            profile_revision="1",
            descriptor_sha256="2" * 64,
        ),
    )

    parsed = build_parsed_knowledge_revision(
        revision=rev,
        entities=entities,
        assertions=assertions,
        evidence=evidence,
    )

    # Conflicting assertions for project ownership both remain in the parsed model
    a_owns = parsed.get_assertion("asrt:belief-owns")
    b_owns = parsed.get_assertion("asrt:fact-owns")
    retracted = parsed.get_assertion("asrt:retracted-rumor")

    assert a_owns is not None and a_owns.metadata.standing == KnowledgeStanding.PROVISIONAL
    assert b_owns is not None and b_owns.metadata.standing == KnowledgeStanding.ESTABLISHED
    assert retracted is not None and retracted.metadata.standing == KnowledgeStanding.RETRACTED


def test_38_no_public_v0_contract_schema_changes() -> None:
    bundle_path = CONTRACTS_DIR / "dm_vnext_contract_v1.json"
    raw_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert raw_bundle["bundle_schema"] == "dm_vnext_contract_bundle_v1"
    assert raw_bundle["contract_family"] == "dungeonmind-vnext"
    assert raw_bundle["contract_revision"] == "v1"


def test_39_v0_aggregate_remains_exact() -> None:
    from scripts.generate_vnext_contract_bundle import make_bundle

    bundle_path = CONTRACTS_DIR / "dm_vnext_contract_v1.json"
    raw_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert raw_bundle["aggregate_sha256"] == CANONICAL_V0_AGGREGATE

    # Verify recomputation without aggregate_sha256 matches canonical aggregate
    bundle_without_agg = {k: v for k, v in raw_bundle.items() if k != "aggregate_sha256"}
    assert sha256(canonical_json(bundle_without_agg)) == CANONICAL_V0_AGGREGATE

    # Verify freshly generated bundle matches canonical aggregate
    generated = make_bundle()
    assert generated["aggregate_sha256"] == CANONICAL_V0_AGGREGATE


def test_40_10k_benchmark_artifact_validity() -> None:
    bench_path = BENCHMARKS_DIR / "vnext_parsed_knowledge_revision_10k_v1.json"
    assert bench_path.exists(), f"Benchmark artifact {bench_path} does not exist"
    data = json.loads(bench_path.read_text(encoding="utf-8"))

    assert data["benchmark_schema"] == "vnext_parsed_revision_benchmark_v1"
    assert data["workload"]["size"] == 10000
    assert data["cardinalities"]["assertion_count"] == 10000
    assert data["cardinalities"]["entity_count"] == 5000
    assert data["cardinalities"]["evidence_count"] == 2500
    assert data["cardinalities"]["alias_count"] == 2000
    assert len(data["semantic_digest"]) == 64
    assert len(data["compatibility_key"]) == 64
    assert data["build_elapsed_ms"] > 0
    assert data["peak_traced_memory_mb"] > 0
    for lane in [
        "exact_entity_lookup",
        "subject_assertion_lookup",
        "adjacency_lookup",
        "evidence_supporter_lookup",
        "alias_exact_lookup",
        "literal_exact_lookup",
        "lexical_candidate_lookup",
    ]:
        assert lane in data["lookup_latencies_us"]
        assert data["lookup_latencies_us"][lane]["p50_us"] > 0


def test_41_deliberate_post_build_mutation_of_domain_metadata_and_temporal_payload() -> None:
    rev = _make_base_revision()
    dm_payload = {"policy_level": 4, "allowed_roles": ["admin", "audit"]}
    temporal_payload = {"fiscal_year": 2026, "milestones": ["q1", "q2"]}
    dm_list = [
        DomainMetadataEntry(
            schema="corp:policy",
            payload=dm_payload,
        )
    ]
    a = Assertion(
        assertion_id="asrt:domain-meta-test",
        subject_entity_id="ent:alice",
        predicate="corp:role",
        value=LiteralValue(value="admin"),
        metadata=AssertionMetadata(
            scope=[],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="corp:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=[],
            temporal_scope=DomainTemporalScope(
                schema="corp:fiscal_calendar",
                payload=temporal_payload,
            ),
            domain_metadata=dm_list,
        ),
    )
    parsed = build_parsed_knowledge_revision(
        revision=rev,
        entities=[Entity(entity_id="ent:alice")],
        assertions=[a],
    )
    digest_before = parsed.semantic_digest

    # Deliberately mutate domain metadata payload in place
    dm_payload["policy_level"] = 999
    dm_payload["allowed_roles"].append("POISON")

    # Deliberately mutate temporal scope payload in place
    temporal_payload["fiscal_year"] = 1800
    temporal_payload["milestones"].clear()

    # Deliberately mutate caller's domain metadata list
    dm_list.append(DomainMetadataEntry(schema="corp:extra", payload={}))

    # Assert parsed model remained completely unchanged
    parsed_asrt = parsed.get_assertion("asrt:domain-meta-test")
    assert parsed_asrt is not None
    assert len(parsed_asrt.metadata.domain_metadata) == 1
    dm_entry = parsed_asrt.metadata.domain_metadata[0]
    thawed_dm = thaw_json_value(dm_entry.payload)
    assert thawed_dm["policy_level"] == 4
    assert thawed_dm["allowed_roles"] == ["admin", "audit"]

    assert isinstance(parsed_asrt.metadata.temporal_scope, ParsedDomainTemporalScope)
    thawed_temporal = thaw_json_value(parsed_asrt.metadata.temporal_scope.payload)
    assert thawed_temporal["fiscal_year"] == 2026
    assert thawed_temporal["milestones"] == ["q1", "q2"]

    assert parsed.semantic_digest == digest_before

    # Attempt mutation on parsed domain metadata payload itself
    with pytest.raises(TypeError):
        dm_entry.payload["poison"] = "val"  # type: ignore[index]


def test_42_fail_closed_on_malformed_visibility_variant() -> None:
    rev = _make_base_revision()
    a = Assertion(
        assertion_id="asrt:malformed-vis",
        subject_entity_id="ent:alice",
        predicate="corp:role",
        value=LiteralValue(value="admin"),
        metadata=AssertionMetadata(
            scope=[],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="corp:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=[],
            temporal_scope=TimelessTemporalScope(),
            domain_metadata=[],
        ),
    )
    # Deliberately mutate visibility to an unsupported object before build
    a.metadata.visibility = "unsupported_public"  # type: ignore[assignment]
    with pytest.raises(RevisionStructuralIntegrityError, match="visibility variant"):
        build_parsed_knowledge_revision(
            revision=rev,
            entities=[Entity(entity_id="ent:alice")],
            assertions=[a],
        )


def test_43_fail_closed_on_malformed_temporal_scope_variant() -> None:
    rev = _make_base_revision()
    a = Assertion(
        assertion_id="asrt:malformed-temporal",
        subject_entity_id="ent:alice",
        predicate="corp:role",
        value=LiteralValue(value="admin"),
        metadata=AssertionMetadata(
            scope=[],
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="corp:fact",
            standing=KnowledgeStanding.ESTABLISHED,
            evidence_ref_ids=[],
            temporal_scope=TimelessTemporalScope(),
            domain_metadata=[],
        ),
    )
    # Deliberately mutate temporal scope to an unsupported object before build
    a.metadata.temporal_scope = "unsupported_timeless"  # type: ignore[assignment]
    with pytest.raises(RevisionStructuralIntegrityError, match="temporal scope variant"):
        build_parsed_knowledge_revision(
            revision=rev,
            entities=[Entity(entity_id="ent:alice")],
            assertions=[a],
        )


def test_44_compatibility_key_covers_all_pinned_ref_identity_components() -> None:
    parsed = _build_standard_parsed()
    base_ident = parsed.identity
    base_key = parsed.compatibility_key
    assert compute_compatibility_key(base_ident) == base_key

    # 1. Mutate graph_schema
    ident_schema = copy.deepcopy(base_ident)
    object.__setattr__(ident_schema, "graph_schema", "dm_vnext_graph_v2")
    assert compute_compatibility_key(ident_schema) != base_key

    # 2. Mutate domain_contract_ref.domain_id
    ident_d_id = copy.deepcopy(base_ident)
    object.__setattr__(
        ident_d_id,
        "domain_contract_ref",
        ParsedDomainContractRef(
            domain_id="mutated.domain",
            domain_revision=base_ident.domain_contract_ref.domain_revision,
            descriptor_sha256=base_ident.domain_contract_ref.descriptor_sha256,
        ),
    )
    assert compute_compatibility_key(ident_d_id) != base_key

    # 3. Mutate domain_contract_ref.domain_revision
    ident_d_rev = copy.deepcopy(base_ident)
    object.__setattr__(
        ident_d_rev,
        "domain_contract_ref",
        ParsedDomainContractRef(
            domain_id=base_ident.domain_contract_ref.domain_id,
            domain_revision="99",
            descriptor_sha256=base_ident.domain_contract_ref.descriptor_sha256,
        ),
    )
    assert compute_compatibility_key(ident_d_rev) != base_key

    # 4. Mutate domain_contract_ref.descriptor_sha256
    ident_d_sha = copy.deepcopy(base_ident)
    object.__setattr__(
        ident_d_sha,
        "domain_contract_ref",
        ParsedDomainContractRef(
            domain_id=base_ident.domain_contract_ref.domain_id,
            domain_revision=base_ident.domain_contract_ref.domain_revision,
            descriptor_sha256="0" * 64,
        ),
    )
    assert compute_compatibility_key(ident_d_sha) != base_key

    # 5. Mutate semantic_profile_ref.profile_id
    ident_p_id = copy.deepcopy(base_ident)
    object.__setattr__(
        ident_p_id,
        "semantic_profile_ref",
        ParsedSemanticProfileRef(
            profile_id="mutated.profile",
            profile_revision=base_ident.semantic_profile_ref.profile_revision,
            descriptor_sha256=base_ident.semantic_profile_ref.descriptor_sha256,
        ),
    )
    assert compute_compatibility_key(ident_p_id) != base_key

    # 6. Mutate semantic_profile_ref.profile_revision
    ident_p_rev = copy.deepcopy(base_ident)
    object.__setattr__(
        ident_p_rev,
        "semantic_profile_ref",
        ParsedSemanticProfileRef(
            profile_id=base_ident.semantic_profile_ref.profile_id,
            profile_revision="99",
            descriptor_sha256=base_ident.semantic_profile_ref.descriptor_sha256,
        ),
    )
    assert compute_compatibility_key(ident_p_rev) != base_key

    # 7. Mutate semantic_profile_ref.descriptor_sha256
    ident_p_sha = copy.deepcopy(base_ident)
    object.__setattr__(
        ident_p_sha,
        "semantic_profile_ref",
        ParsedSemanticProfileRef(
            profile_id=base_ident.semantic_profile_ref.profile_id,
            profile_revision=base_ident.semantic_profile_ref.profile_revision,
            descriptor_sha256="0" * 64,
        ),
    )
    assert compute_compatibility_key(ident_p_sha) != base_key
