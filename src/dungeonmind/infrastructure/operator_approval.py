"""Ed25519 approval verification adapter for Core infrastructure."""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dungeonmind.application.vnext.operator_approval import (
    OperatorApprovalRejectedError,
    TrustedOperatorApproval,
    operator_approval_signing_message,
)
from dungeonmind.domain.canonical import canonical_sha256


class Ed25519OperatorApprovalVerifier:
    """Public-key verifier; the authenticated host exclusively owns the signer."""

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
