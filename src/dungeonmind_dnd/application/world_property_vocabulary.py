"""Pure loaders and assignment validation for world-property vocabularies.

Side-effect-free: package data is read with ``importlib.resources`` only
inside these functions (never at import time). Explicit revision pins only —
never ``latest`` / ``current``.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from pydantic import ValidationError

from dungeonmind.domain.canonical import canonical_sha256

from ..contracts.vocabulary import (
    DndPropertyVocabulary,
    DndVocabularyProperty,
    DndVocabularyRef,
)
from ..domain.errors import DndCandidateValidationError, DndVocabularyIntegrityError
from .world_object_vocabulary import (
    builtin_world_object_v3_vocabulary_ref,
    load_builtin_v3_descriptor,
    load_builtin_world_object_v3_vocabulary,
)
from .world_object_vocabulary import (
    vocabulary_sha256 as world_object_vocabulary_sha256,
)

_VOCABULARY_RESOURCE_DIR = "vocabularies"
_WORLD_PROPERTY_V1_RESOURCE = "world-property-v1.json"

WORLD_PROPERTY_VOCABULARY_ID = "dungeonmind.dnd5e.world_property"
WORLD_PROPERTY_VOCABULARY_REVISION = "world-property-v1"


def _validation_messages(exc: ValidationError) -> list[str]:
    messages = [str(err.get("msg", "invalid")) for err in exc.errors()]
    return list(dict.fromkeys(messages))


def _read_resource_text(directory: str, name: str) -> str:
    return (
        resources.files("dungeonmind_dnd")
        .joinpath(directory)
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def _load_json_resource(directory: str, name: str, *, description: str) -> Any:
    try:
        raw = _read_resource_text(directory, name)
    except OSError as exc:
        raise DndVocabularyIntegrityError(
            f"{description} could not be read",
            details={"reason": type(exc).__name__},
        ) from None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise DndVocabularyIntegrityError(
            f"{description} is not valid JSON",
            details={"reason": "JSONDecodeError"},
        ) from None


def world_property_vocabulary_sha256(vocabulary: DndPropertyVocabulary) -> str:
    return canonical_sha256(vocabulary.model_dump(mode="json"))


def _verify_property_catalog_dependencies(catalog: DndPropertyVocabulary) -> None:
    descriptor = load_builtin_v3_descriptor()
    pinned = catalog.semantic_profile
    if (
        pinned.profile_id != descriptor.profile_id
        or pinned.profile_revision != descriptor.profile_revision
    ):
        raise DndVocabularyIntegrityError(
            "world-property vocabulary profile identity mismatch",
            details={"reason": "profile_identity_mismatch"},
        )
    expected_digest = canonical_sha256(descriptor.model_dump(mode="json"))
    if pinned.descriptor_sha256 != expected_digest:
        raise DndVocabularyIntegrityError(
            "world-property vocabulary profile digest mismatch",
            details={"reason": "profile_digest_mismatch"},
        )

    world_object = load_builtin_world_object_v3_vocabulary()
    expected_ref = builtin_world_object_v3_vocabulary_ref()
    actual_ref = catalog.world_object_vocabulary
    if (
        actual_ref.vocabulary_id != expected_ref.vocabulary_id
        or actual_ref.vocabulary_revision != expected_ref.vocabulary_revision
        or actual_ref.catalog_sha256 != expected_ref.catalog_sha256
    ):
        raise DndVocabularyIntegrityError(
            "world-property vocabulary world-object dependency mismatch",
            details={"reason": "world_object_dependency_mismatch"},
        )
    # Refuse silent widening: dependency digest must match the exact builtin.
    if world_object_vocabulary_sha256(world_object) != expected_ref.catalog_sha256:
        raise DndVocabularyIntegrityError(
            "bundled world-object-v3 digest drift",
            details={"reason": "world_object_digest_drift"},
        )

    kind_terms = {kind.term for kind in world_object.object_kinds}
    predicate_terms = {predicate.term for predicate in world_object.predicates}
    reserved = kind_terms | predicate_terms
    admitted_namespaces = set(descriptor.term_namespaces)

    for prop in catalog.properties:
        ns = prop.term.split(":", 1)[0]
        if ns not in admitted_namespaces:
            raise DndVocabularyIntegrityError(
                "world-property vocabulary admits unknown namespace",
                details={"reason": "namespace_not_admitted", "term": prop.term},
            )
        if prop.term in reserved:
            raise DndVocabularyIntegrityError(
                "property term collides with world-object kind or predicate",
                details={"reason": "term_collision", "term": prop.term},
            )
        for subject_kind in prop.subject_kinds:
            if subject_kind not in kind_terms:
                raise DndVocabularyIntegrityError(
                    "property subject kind missing from pinned world-object vocabulary",
                    details={
                        "reason": "unknown_subject_kind",
                        "term": prop.term,
                        "subject_kind": subject_kind,
                    },
                )


def load_builtin_world_property_vocabulary() -> DndPropertyVocabulary:
    """Immutable world-property-v1 catalog. Explicit pin only — never 'latest'."""
    data = _load_json_resource(
        _VOCABULARY_RESOURCE_DIR,
        _WORLD_PROPERTY_V1_RESOURCE,
        description="bundled world-property-v1 vocabulary catalog",
    )
    try:
        catalog = DndPropertyVocabulary.model_validate(data)
    except ValidationError as exc:
        messages = _validation_messages(exc)
        raise DndVocabularyIntegrityError(
            "bundled world-property-v1 vocabulary catalog failed validation: "
            + "; ".join(messages),
            details={"reason": "ValidationError", "messages": messages},
        ) from None
    if (
        catalog.vocabulary_id != WORLD_PROPERTY_VOCABULARY_ID
        or catalog.vocabulary_revision != WORLD_PROPERTY_VOCABULARY_REVISION
    ):
        raise DndVocabularyIntegrityError(
            "bundled world-property-v1 vocabulary identity mismatch",
            details={"reason": "vocabulary_identity_mismatch"},
        )
    _verify_property_catalog_dependencies(catalog)
    return catalog


def builtin_world_property_vocabulary_ref() -> DndVocabularyRef:
    """Exact world-property-v1 pin. Callers must request this revision explicitly."""
    catalog = load_builtin_world_property_vocabulary()
    return DndVocabularyRef(
        vocabulary_id=catalog.vocabulary_id,
        vocabulary_revision=catalog.vocabulary_revision,
        catalog_sha256=world_property_vocabulary_sha256(catalog),
    )


def _require_property(catalog: DndPropertyVocabulary, property_term: str) -> DndVocabularyProperty:
    for prop in catalog.properties:
        if prop.term == property_term:
            return prop
    raise DndCandidateValidationError(
        "unknown world property term",
        details={"reason": "unknown_property_term", "property_term": property_term},
    )


def _validate_non_empty_string(value: object) -> None:
    if not isinstance(value, str):
        raise DndCandidateValidationError(
            "world property value must be a string",
            details={"reason": "value_type", "expected": "non_empty_string"},
        )
    if not value.strip():
        raise DndCandidateValidationError(
            "world property value must be a non-empty string",
            details={"reason": "value_blank", "expected": "non_empty_string"},
        )


def validate_world_property_assignment(
    *,
    property_term: str,
    subject_kind: str,
    value: object,
) -> None:
    """Fail closed unless term, subject kind, and value satisfy the exact catalog."""
    catalog = load_builtin_world_property_vocabulary()
    world_object = load_builtin_world_object_v3_vocabulary()
    kind_terms = {kind.term for kind in world_object.object_kinds}
    if subject_kind not in kind_terms:
        raise DndCandidateValidationError(
            "subject kind is not in the pinned world-object vocabulary",
            details={"reason": "unknown_subject_kind", "subject_kind": subject_kind},
        )
    prop = _require_property(catalog, property_term)
    if subject_kind not in prop.subject_kinds:
        raise DndCandidateValidationError(
            "subject kind is not admitted for property term",
            details={
                "reason": "subject_kind_not_admitted",
                "property_term": property_term,
                "subject_kind": subject_kind,
            },
        )
    if prop.value_contract == "non_empty_string":
        _validate_non_empty_string(value)
        return
    raise DndCandidateValidationError(
        "unsupported property value contract",
        details={"reason": "unsupported_value_contract", "value_contract": prop.value_contract},
    )
