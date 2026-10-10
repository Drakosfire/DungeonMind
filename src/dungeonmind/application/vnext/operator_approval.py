"""Opaque in-process capability binding a host-authenticated GM to one review."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

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


class OperatorApprovalAuthority:
    """Inject into the trusted host and Core adapter; never bind from HTTP JSON."""

    def __init__(
        self, secret: bytes, *, domain_descriptor_sha256: str,
        allowed_source_terms: frozenset[str], gm_label: str,
    ) -> None:
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("approval secret must be at least 32 bytes")
        if not allowed_source_terms or not gm_label or len(domain_descriptor_sha256) != 64:
            raise ValueError("pinned descriptor, source vocabulary and GM label required")
        self._secret = bytes(secret)
        self.domain_descriptor_sha256 = domain_descriptor_sha256
        self.allowed_source_terms = frozenset(allowed_source_terms)
        self.gm_label = gm_label
        self.source_vocabulary_sha256 = canonical_sha256(sorted(allowed_source_terms))

    @classmethod
    def new_for_process(
        cls, *, domain_descriptor_sha256: str,
        allowed_source_terms: frozenset[str], gm_label: str,
    ) -> OperatorApprovalAuthority:
        return cls(
            secrets.token_bytes(32),
            domain_descriptor_sha256=domain_descriptor_sha256,
            allowed_source_terms=allowed_source_terms,
            gm_label=gm_label,
        )

    @staticmethod
    def _payload(value: TrustedOperatorApproval) -> dict[str, str]:
        return {
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

    def mint_from_authenticated_host(
        self, *, space_id: str, world_id: str, operation_id: str,
        preparation_sha256: str, source_vocabulary_sha256: str,
        actor: str, role: str, auth_method: str,
    ) -> TrustedOperatorApproval:
        """Call only after host session and source_span.approve authorization."""
        if role not in {"owner", "gm"}:
            raise OperatorApprovalRejectedError("GM/owner authority required")
        if any(not isinstance(v, str) or not v.strip() for v in (
            space_id, world_id, operation_id, preparation_sha256,
            source_vocabulary_sha256, actor, auth_method,
        )):
            raise OperatorApprovalRejectedError("approval identity is blank")
        unsigned = TrustedOperatorApproval(
            space_id, world_id, operation_id, preparation_sha256,
            source_vocabulary_sha256, actor, role, auth_method,
            datetime.now(UTC), "",
        )
        return TrustedOperatorApproval(
            space_id, world_id, operation_id, preparation_sha256,
            source_vocabulary_sha256, actor, role, auth_method,
            unsigned.approved_at, self._sign(unsigned),
        )

    def _sign(self, value: TrustedOperatorApproval) -> str:
        digest = canonical_sha256(self._payload(value)).encode("ascii")
        return hmac.new(self._secret, digest, hashlib.sha256).hexdigest()

    def verify(
        self, value: TrustedOperatorApproval, *, space_id: str, world_id: str,
        operation_id: str, preparation_sha256: str,
        source_vocabulary_sha256: str,
    ) -> None:
        if not isinstance(value, TrustedOperatorApproval):
            raise OperatorApprovalRejectedError("in-process host approval required")
        if (
            value.space_id != space_id or value.world_id != world_id
            or value.operation_id != operation_id
            or value.preparation_sha256 != preparation_sha256
            or value.source_vocabulary_sha256 != source_vocabulary_sha256
            or value.role not in {"owner", "gm"}
            or not value.actor.strip() or not value.auth_method.strip()
            or value.approved_at.utcoffset() is None
            or not hmac.compare_digest(value.signature, self._sign(value))
        ):
            raise OperatorApprovalRejectedError("approval authority mismatch")
