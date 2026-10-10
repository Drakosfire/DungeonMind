"""Application contracts for approvals issued by an authenticated external host."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from dungeonmind.domain.canonical import canonical_sha256


class OperatorApprovalRejectedError(ValueError):
    """A host approval is absent, unauthorized, stale or altered."""


@dataclass(frozen=True, slots=True)
class TrustedOperatorApproval:
    space_id: str
    world_id: str
    operation_id: str
    preparation_sha256: str
    source_vocabulary_sha256: str
    actor: str
    role: str
    auth_method: str
    approved_at: datetime
    signature: str


def operator_approval_signing_message(value: TrustedOperatorApproval) -> bytes:
    """Canonical message the authenticated host signs with its private key."""
    payload = {
        "schema": "dm_trusted_operator_source_approval_v1",
        "space_id": value.space_id,
        "world_id": value.world_id,
        "operation_id": value.operation_id,
        "preparation_sha256": value.preparation_sha256,
        "source_vocabulary_sha256": value.source_vocabulary_sha256,
        "actor": value.actor,
        "role": value.role,
        "auth_method": value.auth_method,
        "approved_at": value.approved_at.isoformat(),
    }
    return canonical_sha256(payload).encode("ascii")


class OperatorApprovalVerifier(Protocol):
    """Port implemented by infrastructure from a host-configured public key."""

    domain_descriptor_sha256: str
    allowed_source_terms: frozenset[str]
    gm_label: str
    source_vocabulary_sha256: str

    def verify(
        self,
        value: TrustedOperatorApproval,
        *,
        space_id: str,
        world_id: str,
        operation_id: str,
        preparation_sha256: str,
        source_vocabulary_sha256: str,
    ) -> None: ...
