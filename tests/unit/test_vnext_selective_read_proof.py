"""Exact pin and selective fact/bucket integrity."""

import json
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from dungeonmind.application.vnext._selective_read_proof import (
    build_selective_read_proof,
    open_selective_read_proof,
    verify_selective_buckets,
    verify_selective_records,
)
from dungeonmind.application.vnext.records import StoredKnowledgeRevision
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.common import (
    EpistemicBasis,
    KnowledgeStanding,
    PublicVisibility,
    TimelessTemporalScope,
)
from dungeonmind.contracts.vnext.domain import (
    Assertion,
    AssertionMetadata,
    DomainContractRef,
    Entity,
    EntityRefValue,
)
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError


@pytest.fixture
def sample():
    entities = [Entity(entity_id=name).model_dump(mode="json") for name in ("a", "b")]
    edge = Assertion(
        assertion_id="ab",
        subject_entity_id="a",
        predicate="demo:edge",
        value=EntityRefValue(entity_id="b"),
        metadata=AssertionMetadata(
            standing=KnowledgeStanding.ESTABLISHED,
            visibility=PublicVisibility(),
            epistemic_basis=EpistemicBasis.ASSERTED,
            claim_mode="demo:fact",
            temporal_scope=TimelessTemporalScope(),
        ),
    ).model_dump(mode="json")
    payload = dict(entities=entities, assertions=[edge], aliases=[], evidence=[])
    revision = KnowledgeRevision(
        space_id="space",
        revision_id="revision",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        operation_ids=["op:seed"],
        graph_schema="dm_vnext_graph_v1",
        graph_payload_sha256=canonical_sha256(payload),
        domain_contract_ref=DomainContractRef(
            domain_id="demo.world",
            domain_revision="1",
            descriptor_sha256="a" * 64,
        ),
        semantic_profile_ref=SemanticProfileRef(
            profile_id="demo.world.profile",
            profile_revision="1",
            descriptor_sha256="b" * 64,
        ),
    )
    content = build_selective_read_proof(StoredKnowledgeRevision.seal(revision, payload))
    return revision, edge, content


def open_trusted(revision, content):
    return open_selective_read_proof(
        content,
        expected_sha256=sha256(content).hexdigest(),
        revision=revision,
    )


def test_revision_binding_and_independent_digest(sample):
    revision, _, content = sample
    open_trusted(revision, content)
    with pytest.raises(PersistenceIntegrityError, match="revision binding"):
        open_trusted(revision.model_copy(update={"revision_id": "other"}), content)
    with pytest.raises(PersistenceIntegrityError, match="revision binding"):
        open_trusted(revision.model_copy(update={"operation_ids": ["other"]}), content)

    changed = json.loads(content)
    changed["buckets"]["outgoing"].clear()
    with pytest.raises(PersistenceIntegrityError, match="digest mismatch"):
        open_selective_read_proof(
            json.dumps(changed).encode(),
            expected_sha256=sha256(content).hexdigest(),
            revision=revision,
        )


def test_bucket_completeness_and_exact_direction(sample):
    revision, _, content = sample
    proof = open_trusted(revision, content)
    verify_selective_buckets(proof, "outgoing", ["a", "b"], [("a", [["ab", "a", "b"]]), ("b", [])])
    verify_selective_buckets(proof, "incoming", ["b"], [("b", [["ab", "a", "b"]])])
    with pytest.raises(PersistenceIntegrityError, match="missing or duplicated"):
        verify_selective_buckets(proof, "outgoing", ["a", "b"], [("a", [["ab", "a", "b"]])])
    with pytest.raises(PersistenceIntegrityError, match="seal mismatch"):
        verify_selective_buckets(proof, "outgoing", ["a"], [("a", [])])
    with pytest.raises(PersistenceIntegrityError, match="seal mismatch"):
        verify_selective_buckets(proof, "outgoing", ["a"], [("a", [["ab", "a", "wrong"]])])


def test_selected_fact_integrity_and_absence(sample):
    revision, edge, content = sample
    proof = open_trusted(revision, content)
    verify_selective_records(proof, "assertions", ["ab", "absent"], [("ab", edge)])
    with pytest.raises(PersistenceIntegrityError, match="missing or unexpected"):
        verify_selective_records(proof, "assertions", ["ab"], [])
    with pytest.raises(PersistenceIntegrityError, match="seal mismatch"):
        verify_selective_records(
            proof, "assertions", ["ab"], [("ab", edge | {"subject_entity_id": "wrong"})]
        )
