"""One-world bearer access binding for the publication transport."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from ..contracts.review_publication_transport import FinalizedReviewPublicationRequest
from ..domain.errors import CapabilityDeniedError


def _denied() -> CapabilityDeniedError:
    return CapabilityDeniedError(
        "Publication access denied.",
        details={"reason": "publication_access_denied"},
    )


@dataclass(frozen=True, repr=False)
class PublicationAccessBinding:
    """A configured world and a digest, never the raw bearer secret."""

    world_id: str
    bearer_token_sha256: str

    def __repr__(self) -> str:
        return (
            "PublicationAccessBinding("
            "world_id=<redacted>, bearer_token_sha256=<redacted>)"
        )

    @classmethod
    def from_secret(cls, world_id: str, bearer_token: str) -> PublicationAccessBinding:
        if not world_id.strip():
            raise ValueError("publication world must be non-blank")
        if not bearer_token.strip():
            raise ValueError("publication bearer token must be non-blank")
        return cls(
            world_id=world_id,
            bearer_token_sha256=hashlib.sha256(
                bearer_token.encode("utf-8")
            ).hexdigest(),
        )


def authorize_publication_request(
    request: FinalizedReviewPublicationRequest,
    *,
    authorization_header: str | None,
    binding: PublicationAccessBinding,
) -> FinalizedReviewPublicationRequest:
    """Authorize one exact bearer/world binding without exposing its secret."""

    if authorization_header is None or not authorization_header.startswith("Bearer "):
        raise _denied()
    supplied_token = authorization_header.removeprefix("Bearer ")
    if not supplied_token or any(character.isspace() for character in supplied_token):
        raise _denied()
    supplied_digest = hashlib.sha256(supplied_token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(supplied_digest, binding.bearer_token_sha256):
        raise _denied()
    if request.world_id != binding.world_id:
        raise _denied()
    return request.model_copy(deep=True)
