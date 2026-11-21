"""Native source authority without an assertion graph open."""

from collections.abc import Callable, Sequence

from dungeonmind.application.vnext._selective_read_proof import (
    open_selective_read_proof,
    verify_selective_records,
)
from dungeonmind.application.vnext.builder import _parse_evidence, _parse_revision_identity
from dungeonmind.application.vnext.frozen_json import FrozenDict
from dungeonmind.application.vnext.native_source_access import (
    NativeTextSourceAccessContext,
    NativeTextSourceMembership,
    _verified_source_domain,
)
from dungeonmind.contracts.semantic_profile import SemanticProfileRef
from dungeonmind.contracts.vnext.domain import DomainContractDescriptor, DomainContractRef
from dungeonmind.contracts.vnext.source import EvidenceRefV3
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
) -> NativeTextSourceAccessContext | None:
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
        domain = _verified_source_domain(revision, domain_contract)
        proof = open_selective_read_proof(content, expected_sha256=digest, revision=revision)
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
        membership = NativeTextSourceMembership(_parse_revision_identity(revision), evidence)

    return NativeTextSourceAccessContext(
        space_id=space_id,
        revision_id=revision_id,
        parsed=membership,
        source_view=repository.open_native_source_view(space_id),
        audience_labels=frozenset(audience_labels),
        declared_visibility_labels=frozenset(domain.visibility_labels),
        source_annotation_schemas=frozenset(domain.source_annotation_schemas),
    )
