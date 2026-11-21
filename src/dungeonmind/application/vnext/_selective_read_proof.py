"""Revision-local completeness proofs for a derived selective read projection.

A publisher derives this directory from verified immutable revision facts.
Readers authenticate it against an expected digest obtained from the authority
that activated the projection. The projection cannot authenticate itself.
Source admission and current source visibility are checked separately.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Literal

from dungeonmind.contracts.base import DungeonMindModel
from dungeonmind.contracts.vnext.common import Sha256Hex
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.domain.canonical import canonical_json, canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError

from ._read_artifact import parse_verified_source_rows
from .materialization import NATIVE_VNEXT_GRAPH_SCHEMA
from .records import ParsedEntityRefValue, StoredKnowledgeRevision

_RECORD_IDS = {
    "entities": "entity_id",
    "assertions": "assertion_id",
    "aliases": "alias_id",
    "evidence": "evidence_ref_id",
}
_EMPTY_BUCKET_DIGEST = canonical_sha256([])


_BUCKET_FAMILIES = frozenset(
    ("lexical", "predicate", "term", "subject", "aliases", "outgoing", "incoming")
)


class _SelectiveReadProofWire(DungeonMindModel):
    format_version: Literal["dm_selective_read_proof_v1"]
    space_id: str
    revision_id: str
    revision_sha256: Sha256Hex
    payload_sha256: Sha256Hex
    records: dict[str, dict[str, Sha256Hex]]
    buckets: dict[str, dict[str, Sha256Hex]]


@dataclass(frozen=True, slots=True)
class SelectiveReadProof:
    """Authenticated, deeply immutable seal directory for the checked pin."""

    records: Mapping[str, Mapping[str, str]]
    buckets: Mapping[str, Mapping[str, str]]


def build_selective_read_proof(stored: StoredKnowledgeRevision) -> bytes:
    """Derive complete posting and fact seals from one verified native revision."""
    revision = stored.revision
    if (
        revision.graph_schema != NATIVE_VNEXT_GRAPH_SCHEMA
        or revision.graph_payload_sha256 != stored.graph_payload_sha256
    ):
        raise PersistenceIntegrityError("selective proof requires an exact native revision")
    rows = stored.graph_payload
    records = {
        table: {row[key]: canonical_sha256(row) for row in rows[table]}
        for table, key in _RECORD_IDS.items()
    }
    parsed = parse_verified_source_rows(stored, rows)
    if parsed is None:
        raise PersistenceIntegrityError("selective proof requires native revision facts")
    buckets = {
        name: {key: canonical_sha256(list(ids)) for key, ids in index.items() if ids}
        for name, index in (
            ("lexical", parsed.lexical_assertion_index),
            ("predicate", parsed.predicate_assertion_index),
            ("term", parsed.term_ref_assertion_index),
            ("subject", parsed.assertions_by_subject),
            ("aliases", parsed.aliases_by_entity),
        )
    }
    for name, index in (
        ("outgoing", parsed.entity_ref_outgoing_assertions),
        ("incoming", parsed.entity_ref_incoming_assertions),
    ):
        sealed: dict[str, str] = {}
        for key, ids in index.items():
            if not ids:
                continue
            entries = []
            for identifier in ids:
                assertion = parsed.assertions_by_id[identifier]
                if not isinstance(assertion.value, ParsedEntityRefValue):
                    raise PersistenceIntegrityError("selective edge bucket contains a non-edge")
                entries.append([identifier, assertion.subject_entity_id, assertion.value.entity_id])
            sealed[key] = canonical_sha256(entries)
        buckets[name] = sealed

    proof = _SelectiveReadProofWire(
        format_version="dm_selective_read_proof_v1",
        space_id=revision.space_id,
        revision_id=revision.revision_id,
        revision_sha256=canonical_sha256(revision.model_dump(mode="json")),
        payload_sha256=stored.graph_payload_sha256,
        records=records,
        buckets=buckets,
    )
    return canonical_json(proof.model_dump(mode="json")).encode("utf-8")


def open_selective_read_proof(
    content: bytes,
    *,
    expected_sha256: str,
    revision: KnowledgeRevision,
) -> SelectiveReadProof:
    if sha256(content).hexdigest() != expected_sha256:
        raise PersistenceIntegrityError("selective proof digest mismatch")
    try:
        proof = _SelectiveReadProofWire.model_validate_json(content)
    except ValueError as exc:
        raise PersistenceIntegrityError("selective proof is malformed") from exc
    if (proof.space_id, proof.revision_id, proof.revision_sha256, proof.payload_sha256) != (
        revision.space_id,
        revision.revision_id,
        canonical_sha256(revision.model_dump(mode="json")),
        revision.graph_payload_sha256,
    ):
        raise PersistenceIntegrityError("selective proof revision binding mismatch")
    if proof.records.keys() != _RECORD_IDS.keys() or proof.buckets.keys() != _BUCKET_FAMILIES:
        raise PersistenceIntegrityError("selective proof families are incomplete or unknown")
    return SelectiveReadProof(
        records=MappingProxyType(
            {key: MappingProxyType(value) for key, value in proof.records.items()}
        ),
        buckets=MappingProxyType(
            {key: MappingProxyType(value) for key, value in proof.buckets.items()}
        ),
    )


def verify_selective_buckets(
    proof: SelectiveReadProof,
    family: str,
    requested: Sequence[str],
    rows: Sequence[tuple[str, Sequence[Any]]],
) -> None:
    """Validate the complete ordered collection for each requested key."""
    seals = proof.buckets[family]
    keys = set(requested)
    if len(rows) != len(keys) or {key for key, _ in rows} != keys:
        raise PersistenceIntegrityError("selective posting buckets missing or duplicated")
    for key, ordered in rows:
        if canonical_sha256(list(ordered)) != seals.get(key, _EMPTY_BUCKET_DIGEST):
            raise PersistenceIntegrityError("selective posting bucket seal mismatch")


def verify_selective_records(
    proof: SelectiveReadProof,
    table: str,
    requested: Sequence[str],
    rows: Sequence[tuple[str, Mapping[str, Any]]],
) -> None:
    """Validate selected facts, including authenticated absence of a record."""
    seals = proof.records[table]
    expected = set(requested) & seals.keys()
    if len(rows) != len(expected) or {key for key, _ in rows} != expected:
        raise PersistenceIntegrityError("selective records missing or unexpected")
    for key, record in rows:
        if canonical_sha256(dict(record)) != seals[key]:
            raise PersistenceIntegrityError("selective record seal mismatch")
