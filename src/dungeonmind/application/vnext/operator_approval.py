"""Core-side verification of approvals signed by a trusted external host.

The authenticated host owns the Ed25519 private key and the only issuance path.
Core receives only the public key and cannot mint approvals from request fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

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


class OperatorApprovalVerifier:
    """Core verification key and pinned domain policy; contains no signing key."""

    def __init__(
        self,
        public_key: bytes,
        *,
        domain_descriptor_sha256: str,
        allowed_source_terms: frozenset[str],
        gm_label: str,
    ) -> None:
        if not isinstance(public_key, bytes) or len(public_key) != 32:
            raise ValueError("Ed25519 public key must be 32 bytes")
        if not allowed_source_terms or not gm_label or len(domain_descriptor_sha256) != 64:
            raise ValueError("pinned descriptor, source vocabulary and GM label required")
        self._public_key = Ed25519PublicKey.from_public_bytes(public_key)
        self.domain_descriptor_sha256 = domain_descriptor_sha256
        self.allowed_source_terms = frozenset(allowed_source_terms)
        self.gm_label = gm_label
        self.source_vocabulary_sha256 = canonical_sha256(sorted(allowed_source_terms))

    def verify(
        self,
        value: TrustedOperatorApproval,
        *,
        space_id: str,
        world_id: str,
        operation_id: str,
        preparation_sha256: str,
        source_vocabulary_sha256: str,
    ) -> None:
        if not isinstance(value, TrustedOperatorApproval):
            raise OperatorApprovalRejectedError("signed authenticated-host approval required")
        if (
            value.space_id != space_id
            or value.world_id != world_id
            or value.operation_id != operation_id
            or value.preparation_sha256 != preparation_sha256
            or value.source_vocabulary_sha256 != source_vocabulary_sha256
            or value.role not in {"owner", "gm"}
            or not value.actor.strip()
            or not value.auth_method.strip()
            or value.approved_at.utcoffset() is None
        ):
            raise OperatorApprovalRejectedError("approval authority mismatch")
        try:
            signature = bytes.fromhex(value.signature)
            self._public_key.verify(signature, operator_approval_signing_message(value))
        except (InvalidSignature, ValueError) as exc:
            raise OperatorApprovalRejectedError("approval signature is invalid") from exc
