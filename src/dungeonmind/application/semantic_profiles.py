"""Application port and helpers for semantic profile resolution."""

from __future__ import annotations

import re
from typing import Protocol

from ..contracts.semantic_profile import SemanticProfileDescriptor, SemanticProfileRef
from ..domain.canonical import canonical_sha256
from ..domain.errors import (
    SemanticProfileIntegrityError,
    SemanticProfileNotFoundError,
    SemanticTermValidationError,
)

# namespace:local — lowercase; letters/numbers/_/-/.; exactly one colon
_QUALIFIED_TERM = re.compile(
    r"^(?P<namespace>[a-z0-9]+(?:[._-][a-z0-9]+)*)"
    r":"
    r"(?P<local>[a-z0-9]+(?:[._-][a-z0-9]+)*)$"
)


class SemanticProfileRegistry(Protocol):
    def get(
        self, profile_id: str, profile_revision: str
    ) -> SemanticProfileDescriptor | None: ...


def descriptor_sha256(descriptor: SemanticProfileDescriptor) -> str:
    """Content digest of a descriptor's canonical JSON form."""
    return canonical_sha256(descriptor.model_dump(mode="json"))


def parse_qualified_term(term: str) -> tuple[str, str]:
    """Split ``namespace:local`` or raise ``SemanticTermValidationError``."""
    if not isinstance(term, str) or not term:
        raise SemanticTermValidationError(
            "semantic term must be a non-empty qualified string",
            details={"term": term},
        )
    if term != term.casefold():
        raise SemanticTermValidationError(
            "semantic term must be lowercase",
            details={"term": term},
        )
    if term.count(":") != 1:
        raise SemanticTermValidationError(
            "semantic term must contain exactly one ':'",
            details={"term": term},
        )
    match = _QUALIFIED_TERM.fullmatch(term)
    if match is None:
        raise SemanticTermValidationError(
            "semantic term must match namespace:local "
            "(lowercase letters, digits, '.', '_', '-')",
            details={"term": term},
        )
    return match.group("namespace"), match.group("local")


def validate_qualified_term(
    term: str,
    descriptor: SemanticProfileDescriptor,
    *,
    field_name: str,
) -> str:
    """Parse and admit ``term`` against ``descriptor.term_namespaces``."""
    namespace, _local = parse_qualified_term(term)
    if namespace not in descriptor.term_namespaces:
        raise SemanticTermValidationError(
            f"{field_name} namespace is not admitted by the pinned semantic profile",
            details={
                "field": field_name,
                "term": term,
                "namespace": namespace,
                "profile_id": descriptor.profile_id,
                "profile_revision": descriptor.profile_revision,
            },
        )
    return term


def resolve_and_verify_profile(
    ref: SemanticProfileRef,
    registry: SemanticProfileRegistry,
) -> SemanticProfileDescriptor:
    """Resolve ``ref`` from ``registry`` and verify descriptor digest."""
    descriptor = registry.get(ref.profile_id, ref.profile_revision)
    if descriptor is None:
        raise SemanticProfileNotFoundError(
            "semantic profile not found in registry",
            details={
                "profile_id": ref.profile_id,
                "profile_revision": ref.profile_revision,
            },
        )
    if (
        descriptor.profile_id != ref.profile_id
        or descriptor.profile_revision != ref.profile_revision
    ):
        raise SemanticProfileIntegrityError(
            "semantic profile descriptor identity mismatch",
            details={
                "profile_id": ref.profile_id,
                "profile_revision": ref.profile_revision,
            },
        )
    digest = descriptor_sha256(descriptor)
    if digest != ref.descriptor_sha256:
        raise SemanticProfileIntegrityError(
            "semantic profile descriptor digest mismatch",
            details={
                "profile_id": ref.profile_id,
                "profile_revision": ref.profile_revision,
                "expected_sha256": ref.descriptor_sha256,
                "actual_sha256": digest,
            },
        )
    return descriptor
