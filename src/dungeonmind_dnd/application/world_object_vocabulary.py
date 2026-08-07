"""Pure loaders for the world-object vocabulary catalog.

Side-effect-free: package data is read with ``importlib.resources`` only
inside these functions (never at import time).
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from pydantic import ValidationError

from dungeonmind.contracts.semantic_profile import SemanticProfileDescriptor
from dungeonmind.domain.canonical import canonical_sha256

from ..contracts.vocabulary import DndSemanticVocabulary, DndVocabularyRef
from ..domain.errors import DndVocabularyIntegrityError

_PROFILE_RESOURCE_DIR = "profiles"
_PROFILE_V3_RESOURCE = "dnd5e-v3.json"
_VOCABULARY_RESOURCE_DIR = "vocabularies"
_WORLD_OBJECT_VOCABULARY_RESOURCE = "world-object-v1.json"

WORLD_OBJECT_VOCABULARY_ID = "dungeonmind.dnd5e.world_object"
WORLD_OBJECT_VOCABULARY_REVISION = "world-object-v1"


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


def load_builtin_v3_descriptor() -> SemanticProfileDescriptor:
    data = _load_json_resource(
        _PROFILE_RESOURCE_DIR,
        _PROFILE_V3_RESOURCE,
        description="bundled dnd5e-v3 profile descriptor",
    )
    try:
        return SemanticProfileDescriptor.model_validate(data)
    except ValidationError as exc:
        messages = _validation_messages(exc)
        raise DndVocabularyIntegrityError(
            "bundled dnd5e-v3 profile descriptor failed validation: "
            + "; ".join(messages),
            details={"reason": "ValidationError", "messages": messages},
        ) from None


def vocabulary_sha256(vocabulary: DndSemanticVocabulary) -> str:
    return canonical_sha256(vocabulary.model_dump(mode="json"))


def _verify_vocabulary_against_descriptor(
    catalog: DndSemanticVocabulary,
    descriptor: SemanticProfileDescriptor,
) -> None:
    pinned = catalog.semantic_profile
    if (
        pinned.profile_id != descriptor.profile_id
        or pinned.profile_revision != descriptor.profile_revision
    ):
        raise DndVocabularyIntegrityError(
            "world-object vocabulary profile identity mismatch",
            details={"reason": "profile_identity_mismatch"},
        )
    expected_digest = canonical_sha256(descriptor.model_dump(mode="json"))
    if pinned.descriptor_sha256 != expected_digest:
        raise DndVocabularyIntegrityError(
            "world-object vocabulary profile digest mismatch",
            details={"reason": "profile_digest_mismatch"},
        )
    admitted = set(descriptor.term_namespaces)
    for kind in catalog.object_kinds:
        ns = kind.term.split(":", 1)[0]
        if ns not in admitted:
            raise DndVocabularyIntegrityError(
                "world-object vocabulary admits unknown namespace",
                details={"reason": "namespace_not_admitted"},
            )
    for predicate in catalog.predicates:
        ns = predicate.term.split(":", 1)[0]
        if ns not in admitted:
            raise DndVocabularyIntegrityError(
                "world-object vocabulary admits unknown namespace",
                details={"reason": "namespace_not_admitted"},
            )


def load_builtin_world_object_vocabulary() -> DndSemanticVocabulary:
    descriptor = load_builtin_v3_descriptor()
    data = _load_json_resource(
        _VOCABULARY_RESOURCE_DIR,
        _WORLD_OBJECT_VOCABULARY_RESOURCE,
        description="bundled world-object vocabulary catalog",
    )
    try:
        catalog = DndSemanticVocabulary.model_validate(data)
    except ValidationError as exc:
        messages = _validation_messages(exc)
        raise DndVocabularyIntegrityError(
            "bundled world-object vocabulary catalog failed validation: "
            + "; ".join(messages),
            details={"reason": "ValidationError", "messages": messages},
        ) from None
    _verify_vocabulary_against_descriptor(catalog, descriptor)
    if (
        catalog.vocabulary_id != WORLD_OBJECT_VOCABULARY_ID
        or catalog.vocabulary_revision != WORLD_OBJECT_VOCABULARY_REVISION
    ):
        raise DndVocabularyIntegrityError(
            "bundled world-object vocabulary identity mismatch",
            details={"reason": "vocabulary_identity_mismatch"},
        )
    return catalog


def builtin_world_object_vocabulary_ref() -> DndVocabularyRef:
    catalog = load_builtin_world_object_vocabulary()
    return DndVocabularyRef(
        vocabulary_id=catalog.vocabulary_id,
        vocabulary_revision=catalog.vocabulary_revision,
        catalog_sha256=vocabulary_sha256(catalog),
    )
