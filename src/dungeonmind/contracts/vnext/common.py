"""Domain-neutral vNext contract values and shared validation."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ..base import DungeonMindModel

JsonValue = Any
_TERM = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*:[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _json_value(value: Any) -> Any:
    def check(item: Any) -> None:
        if item is None or isinstance(item, (str, bool, int)):
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("JSON values must contain finite numbers")
            return
        if isinstance(item, list):
            for child in item:
                check(child)
            return
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                check(child)
            return
        raise ValueError("value is not canonical JSON-compatible")

    check(value)
    return value


def _nonblank(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be a non-blank string")
    return value


def _sha256_hex(value: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError("must be a lowercase hex SHA-256 digest")
    return value


def _unique(values: list[str], field_name: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique values")
    return values


QualifiedTerm = Annotated[
    str,
    StringConstraints(pattern=_TERM.pattern, min_length=3),
]

NonBlankId = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_nonblank),
]

Sha256Hex = Annotated[
    str,
    StringConstraints(min_length=64, max_length=64, pattern=_SHA.pattern),
    AfterValidator(_sha256_hex),
]


class KnowledgeStanding(StrEnum):
    ESTABLISHED = "established"
    PROVISIONAL = "provisional"
    RETRACTED = "retracted"


class EpistemicBasis(StrEnum):
    ASSERTED = "asserted"
    INFERRED = "inferred"
    SPECULATIVE = "speculative"


class DomainMetadataEntry(DungeonMindModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    schema_term: QualifiedTerm = Field(alias="schema")
    payload: JsonValue

    _payload = field_validator("payload")(_json_value)


class ScopeBinding(DungeonMindModel):
    axis: QualifiedTerm
    value: NonBlankId


class ScopeSelector(DungeonMindModel):
    include_unscoped: bool = False
    bindings: list[ScopeBinding] = Field(default_factory=list)
    wildcard_axes: list[QualifiedTerm] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> ScopeSelector:
        keys = [(item.axis, item.value) for item in self.bindings]
        if len(keys) != len(set(keys)):
            raise ValueError("bindings must not contain duplicate axis/value pairs")
        if len(self.wildcard_axes) != len(set(self.wildcard_axes)):
            raise ValueError("wildcard_axes must be unique")
        bound = {item.axis for item in self.bindings}
        if bound & set(self.wildcard_axes):
            raise ValueError("an axis cannot be both bound and wildcarded")
        return self


class PublicVisibility(DungeonMindModel):
    kind: Literal["public"] = "public"


class LabelsAnyVisibility(DungeonMindModel):
    kind: Literal["labels_any"] = "labels_any"
    labels: list[QualifiedTerm] = Field(min_length=1)

    _labels = field_validator("labels")(_unique)


class LabelsAllVisibility(DungeonMindModel):
    kind: Literal["labels_all"] = "labels_all"
    labels: list[QualifiedTerm] = Field(min_length=1)

    _labels = field_validator("labels")(_unique)


VisibilityRequirement = PublicVisibility | LabelsAnyVisibility | LabelsAllVisibility


class UnknownTemporalScope(DungeonMindModel):
    kind: Literal["unknown"] = "unknown"


class TimelessTemporalScope(DungeonMindModel):
    kind: Literal["timeless"] = "timeless"


class UtcIntervalTemporalScope(DungeonMindModel):
    kind: Literal["utc_interval"] = "utc_interval"
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def _bounds(self) -> UtcIntervalTemporalScope:
        if self.valid_from is None and self.valid_until is None:
            raise ValueError("utc_interval requires at least one bound")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until cannot precede valid_from")
        return self


class DomainTemporalScope(DungeonMindModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    kind: Literal["domain_ref"] = "domain_ref"
    schema_term: QualifiedTerm = Field(alias="schema")
    payload: JsonValue

    _payload = field_validator("payload")(_json_value)


TemporalScope = (
    UnknownTemporalScope | TimelessTemporalScope | UtcIntervalTemporalScope | DomainTemporalScope
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha256(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()
