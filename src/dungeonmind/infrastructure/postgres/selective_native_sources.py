"""Native source authority without an assertion graph open."""

from collections.abc import Callable, Iterator, Mapping, Sequence
from hashlib import sha256
from typing import Any

from psycopg import Connection

from dungeonmind.application.vnext._selective_read_proof import (
    SelectiveReadProof,
    open_selective_read_proof,
    verify_selective_records,
)
from dungeonmind.application.vnext.builder import _parse_evidence, _parse_revision_identity
from dungeonmind.application.vnext.frozen_json import FrozenDict
from dungeonmind.application.vnext.native_source_access import (
    NativeTextSourceAccessContext,
    NativeTextSourceCandidate,
    NativeTextSourceMembership,
    _verified_source_domain,
)
from dungeonmind.application.vnext.records import ParsedEvidenceRef
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, DomainContractRef
from dungeonmind.contracts.vnext.knowledge import KnowledgeRevision
from dungeonmind.contracts.vnext.source import EvidenceRefV3
from dungeonmind.domain.canonical import canonical_json
from dungeonmind.domain.errors import PersistenceIntegrityError

from ._selective_revision import _fetch, _load_activation
from .vnext_sources import PostgresNativeSourceEvidenceRepository


def open_selective_native_text_source_access_context(
    repository: PostgresNativeSourceEvidenceRepository,
    *,
    space_id: str,
    revision_id: str,
    domain_contract: (
        DomainContractDescriptor
        | Callable[[DomainContractRef, SemanticProfileRef], DomainContractDescriptor]
    ),
    audience_labels: Sequence[str] = (),
) -> NativeTextSourceAccessContext[NativeTextSourceMembership] | None:
    """Open exact evidence membership, or request the ordinary path if inactive.

    An active projection must prove the complete evidence set, including
    unreferenced source-only evidence. Registration, visibility, current epoch,
    and byte verification stay with the ordinary source authority.
    """
    if not space_id.strip() or not revision_id.strip():
        raise ValueError("selective source access requires an exact revision")
    pin = (space_id, revision_id)
    with repository._database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        activation = _load_activation(connection, pin)
        if activation is None:
            return None
        revision, digest, content = activation
        proof = open_selective_read_proof(content, expected_sha256=digest, revision=revision)
        domain = _verified_source_domain(revision, domain_contract)
        membership = _read_membership(connection, revision, proof)

    return _source_context(repository, membership, domain, audience_labels)


def _read_membership(
    connection: Connection[Any], revision: KnowledgeRevision, proof: SelectiveReadProof,
) -> NativeTextSourceMembership:
    pin = (revision.space_id, revision.revision_id)
    keys = tuple(proof.records["evidence"])
    rows = _fetch(connection, pin, "selective_read_records", "evidence", keys)
    verify_selective_records(proof, "evidence", keys, rows)
    try:
        evidence = FrozenDict([
            (key, _parse_evidence(EvidenceRefV3.model_validate(row))) for key, row in rows
        ])
    except ValueError as exc:
        raise PersistenceIntegrityError("selective source evidence is invalid") from exc
    if any(key != record.evidence_ref_id for key, record in evidence.items()):
        raise PersistenceIntegrityError("selective source evidence identity mismatch")
    return NativeTextSourceMembership(_parse_revision_identity(revision), evidence)



class _VerifiedEvidenceRows(Mapping[str, ParsedEvidenceRef]):
    """Keep sealed evidence as canonical bytes and decode only requested records."""

    def __init__(self, rows: Mapping[str, bytes]) -> None:
        self._rows = FrozenDict(rows)
        self._decoded: dict[str, ParsedEvidenceRef] = {}

    def __len__(self) -> int:
        return len(self._rows)

    def __iter__(self) -> Iterator[str]:
        return iter(self._rows)

    def __contains__(self, key: object) -> bool:
        return key in self._rows

    def __getitem__(self, key: str) -> ParsedEvidenceRef:
        if key not in self._decoded:
            payload = self._rows[key]
            try:
                evidence = _parse_evidence(EvidenceRefV3.model_validate_json(payload))
            except ValueError as exc:
                raise PersistenceIntegrityError("selective source evidence is invalid") from exc
            return self._decoded.setdefault(key, evidence)
        return self._decoded[key]


def _read_source_directory(
    connection: Connection[Any], revision: KnowledgeRevision, proof: SelectiveReadProof,
) -> NativeTextSourceMembership:
    """Derive compact source candidates from the complete authenticated evidence set."""
    pin = (revision.space_id, revision.revision_id)
    seals = proof.records["evidence"]
    rows = _fetch(connection, pin, "selective_read_records", "evidence", tuple(seals))
    if len(rows) != len(seals) or {key for key, _ in rows} != seals.keys():
        raise PersistenceIntegrityError("selective source directory is incomplete")
    packed: dict[str, bytes] = {}
    candidates: list[NativeTextSourceCandidate] = []
    for key, row in rows:
        if not isinstance(row, Mapping) or row.get("evidence_ref_id") != key:
            raise PersistenceIntegrityError("selective source directory evidence identity mismatch")
        payload = canonical_json(dict(row)).encode("utf-8")
        if sha256(payload).hexdigest() != seals[key]:
            raise PersistenceIntegrityError("selective source directory seal mismatch")
        packed[key] = payload
        source_revision = row.get("source_revision_id")
        span = row.get("source_span_ref_id")
        if (
            row.get("can_open_source") is not True or row.get("can_highlight_span") is not True
            or source_revision is None or span is None
        ):
            continue
        artifact = row.get("source_artifact_id")
        if (
            not isinstance(artifact, str) or not artifact
            or not isinstance(source_revision, str) or not source_revision
            or not isinstance(span, str) or not span
        ):
            raise PersistenceIntegrityError("selective source directory binding is invalid")
        annotations = row.get("domain_metadata", [])
        if not isinstance(annotations, list):
            raise PersistenceIntegrityError("selective source directory annotations are invalid")
        schemas: list[str] = []
        for item in annotations:
            schema = item.get("schema", item.get("schema_term")) if isinstance(item, dict) else None
            if not isinstance(schema, str) or not schema:
                raise PersistenceIntegrityError("selective source directory annotation is invalid")
            schemas.append(schema)
        candidates.append(NativeTextSourceCandidate(
            key, artifact, source_revision, span, tuple(sorted(schemas)),
        ))
    return NativeTextSourceMembership(
        _parse_revision_identity(revision), _VerifiedEvidenceRows(packed),
        tuple(sorted(candidates, key=lambda candidate: candidate.evidence_ref_id)),
    )


def _source_context(
    repository: PostgresNativeSourceEvidenceRepository,
    membership: NativeTextSourceMembership,
    domain: DomainContractDescriptor,
    audience_labels: Sequence[str],
) -> NativeTextSourceAccessContext[NativeTextSourceMembership]:
    space_id = membership.identity.space_id
    return NativeTextSourceAccessContext(
        space_id=space_id,
        revision_id=membership.identity.revision_id,
        parsed=membership,
        source_view=repository.open_native_source_view(space_id),
        audience_labels=frozenset(audience_labels),
        declared_visibility_labels=frozenset(domain.visibility_labels),
        source_annotation_schemas=frozenset(domain.source_annotation_schemas),
    )
