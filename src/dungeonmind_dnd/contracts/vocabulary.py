"""D&D semantic vocabulary catalog and vocabulary-reference contracts.

The catalog is profile-owned: it pins one exact ``SemanticProfileRef`` and
enumerates the exact object-kind and predicate terms a candidate producer
may use. Catalog content is immutable at one revision — any term, direction,
range, label, or description change requires a new vocabulary revision and a
new digest. Labels and descriptions are metadata for humans and prompt
rendering; they are never graph truth.
"""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from dungeonmind.contracts.base import DungeonMindModel
from dungeonmind.contracts.semantic_profile import SemanticProfileRef

SEMANTIC_VOCABULARY_SCHEMA = "dmdnd_semantic_vocabulary_v1"
VOCABULARY_REF_SCHEMA = "dmdnd_vocabulary_ref_v1"

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
# Lowercase dotted ids: dungeonmind.dnd5e.threat
_VOCABULARY_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
# Immutable revision tokens (no path/URI/latest)
_VOCABULARY_REVISION = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
# namespace:local — lowercase; letters/numbers/_/-/.; exactly one colon.
# Mirrors the kernel's term shape; duplicated deliberately because the
# one-way dependency forbids importing kernel application helpers.
_QUALIFIED_TERM = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*:[a-z0-9]+(?:[._-][a-z0-9]+)*$")


def qualified_term_namespace(term: str) -> str:
    """Namespace half of a validated ``namespace:local`` term."""
    return term.split(":", 1)[0]


def _reject_locator_like(value: str, *, field_name: str) -> None:
    lowered = value.casefold()
    if lowered == "latest":
        raise ValueError(f"{field_name} must not be 'latest'")
    if any(ch.isspace() for ch in value):
        raise ValueError(f"{field_name} must not contain whitespace")
    if "/" in value or "\\" in value:
        raise ValueError(f"{field_name} must not contain path separators")
    if "://" in value or lowered.startswith(("http:", "https:", "file:", "ftp:")):
        raise ValueError(f"{field_name} must not be a URI")
    if value.endswith(".py") or value.startswith("dungeonmind_dnd."):
        raise ValueError(f"{field_name} must not be a module path")


def _validate_term(value: str, *, field_name: str) -> str:
    if not _QUALIFIED_TERM.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a qualified namespace:local term "
            "(lowercase letters, digits, '.', '_', '-')"
        )
    return value


def _validate_non_empty_text(value: str, *, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value


class DndVocabularyObjectKind(DungeonMindModel):
    """One object-kind term a candidate producer may assign to a node."""

    term: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @field_validator("term")
    @classmethod
    def _validate_term_shape(cls, value: str) -> str:
        return _validate_term(value, field_name="object kind term")

    @field_validator("label", "description")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _validate_non_empty_text(value, field_name="object kind metadata")


class DndVocabularyPredicate(DungeonMindModel):
    """One predicate term plus its closed subject/object kind direction."""

    term: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    subject_kinds: list[str] = Field(min_length=1)
    object_kinds: list[str] = Field(min_length=1)

    @field_validator("term")
    @classmethod
    def _validate_term_shape(cls, value: str) -> str:
        return _validate_term(value, field_name="predicate term")

    @field_validator("label", "description")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _validate_non_empty_text(value, field_name="predicate metadata")

    @field_validator("subject_kinds", "object_kinds")
    @classmethod
    def _validate_kind_terms(cls, value: list[str]) -> list[str]:
        for term in value:
            _validate_term(term, field_name="predicate kind reference")
        return value


class DndSemanticVocabulary(DungeonMindModel):
    """Immutable profile-owned term catalog (one revision, one profile pin)."""

    schema_version: Literal["dmdnd_semantic_vocabulary_v1"] = SEMANTIC_VOCABULARY_SCHEMA
    vocabulary_id: str = Field(min_length=1)
    vocabulary_revision: str = Field(min_length=1)
    semantic_profile: SemanticProfileRef
    object_kinds: list[DndVocabularyObjectKind] = Field(min_length=1)
    predicates: list[DndVocabularyPredicate] = Field(min_length=1)

    @field_validator("vocabulary_id")
    @classmethod
    def _validate_vocabulary_id(cls, value: str) -> str:
        _reject_locator_like(value, field_name="vocabulary_id")
        if not _VOCABULARY_ID.fullmatch(value):
            raise ValueError(
                "vocabulary_id must be lowercase dotted "
                "(letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("vocabulary_revision")
    @classmethod
    def _validate_vocabulary_revision(cls, value: str) -> str:
        _reject_locator_like(value, field_name="vocabulary_revision")
        if not _VOCABULARY_REVISION.fullmatch(value):
            raise ValueError(
                "vocabulary_revision must be a non-empty immutable token "
                "(lowercase letters, digits, '.', '_', '-' only)"
            )
        return value

    @model_validator(mode="after")
    def _terms_unique_disjoint_and_closed(self) -> Self:
        kind_terms = [kind.term for kind in self.object_kinds]
        predicate_terms = [predicate.term for predicate in self.predicates]
        seen: set[str] = set()
        duplicates: set[str] = set()
        for term in kind_terms + predicate_terms:
            if term in seen:
                duplicates.add(term)
            seen.add(term)
        if duplicates:
            raise ValueError(f"duplicate vocabulary terms: {sorted(duplicates)}")
        if set(kind_terms) & set(predicate_terms):
            raise ValueError("object kinds and predicates must be disjoint")
        known_kinds = set(kind_terms)
        for predicate in self.predicates:
            for term in predicate.subject_kinds + predicate.object_kinds:
                if term not in known_kinds:
                    raise ValueError(
                        f"predicate {predicate.term} references unknown object kind {term}"
                    )
        return self


class DndVocabularyRef(DungeonMindModel):
    """Pinned identity of one vocabulary catalog revision (no locators)."""

    schema_version: Literal["dmdnd_vocabulary_ref_v1"] = VOCABULARY_REF_SCHEMA
    vocabulary_id: str = Field(min_length=1)
    vocabulary_revision: str = Field(min_length=1)
    catalog_sha256: str = Field(min_length=64, max_length=64)

    @field_validator("vocabulary_id")
    @classmethod
    def _validate_vocabulary_id(cls, value: str) -> str:
        _reject_locator_like(value, field_name="vocabulary_id")
        if not _VOCABULARY_ID.fullmatch(value):
            raise ValueError(
                "vocabulary_id must be lowercase dotted "
                "(letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("vocabulary_revision")
    @classmethod
    def _validate_vocabulary_revision(cls, value: str) -> str:
        _reject_locator_like(value, field_name="vocabulary_revision")
        if not _VOCABULARY_REVISION.fullmatch(value):
            raise ValueError(
                "vocabulary_revision must be a non-empty immutable token "
                "(lowercase letters, digits, '.', '_', '-' only)"
            )
        return value

    @field_validator("catalog_sha256")
    @classmethod
    def _validate_catalog_sha256(cls, value: str) -> str:
        if not _SHA256_HEX.fullmatch(value):
            raise ValueError("catalog_sha256 must be exactly 64 lowercase hex characters")
        return value
