"""Canonical model serialization and fingerprint helpers for PostgreSQL adapters."""

from __future__ import annotations

import struct
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel

from ...domain.canonical import canonical_sha256
from ...domain.errors import PersistenceIntegrityError

T = TypeVar("T", bound=BaseModel)

_EMBEDDING_RUN_IMMUTABLE_FIELDS: set[str] = {
    "run_id",
    "embedding_model",
    "embedding_model_revision",
    "embedding_dimensions",
    "embedding_recipe",
    "corpus_fingerprint",
    "benchmark_projection_id",
    "world_id",
    "created_at",
    "schema_version",
}


def _float32(value: float) -> float:
    """Round-trip through IEEE-754 binary32 to match pgvector storage."""
    return struct.unpack("!f", struct.pack("!f", float(value)))[0]


def _fingerprint_dump(model: BaseModel, *, include: set[str] | None = None) -> dict[str, Any]:
    dump = (
        model.model_dump(mode="json", include=include)
        if include is not None
        else model.model_dump(mode="json")
    )
    embedding = dump.get("embedding")
    if isinstance(embedding, list):
        dump["embedding"] = [_float32(x) for x in embedding]
    return dump


def model_fingerprint(model: BaseModel) -> str:
    """SHA-256 digest of the model's canonical JSON (not the payload itself)."""
    return canonical_sha256(_fingerprint_dump(model))


def immutable_run_fingerprint(model: BaseModel) -> str:
    """SHA-256 digest of immutable EmbeddingRun creation fields."""
    return canonical_sha256(
        _fingerprint_dump(model, include=_EMBEDDING_RUN_IMMUTABLE_FIELDS)
    )


def dump_payload(model: BaseModel, *, exclude: set[str] | None = None) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude=exclude or set())


def reconstruct(
    model_type: type[T],
    payload: dict[str, Any],
    *,
    expected_fingerprint: str,
    identity: dict[str, Any],
) -> T:
    """Rebuild a contract and fail closed on fingerprint or extracted-column drift."""
    try:
        model = model_type.model_validate(payload)
    except Exception as exc:
        raise PersistenceIntegrityError(
            f"failed to reconstruct {model_type.__name__}: {exc}"
        ) from exc
    actual = model_fingerprint(model)
    if actual != expected_fingerprint:
        raise PersistenceIntegrityError(
            f"{model_type.__name__} record_fingerprint drift for {identity!r}"
        )
    dump = model.model_dump(mode="json")
    for key, expected in identity.items():
        actual_value = dump.get(key)
        if actual_value != expected and _normalize(actual_value) != _normalize(expected):
            raise PersistenceIntegrityError(
                f"{model_type.__name__} column {key!r} disagrees with payload "
                f"({actual_value!r} != {expected!r})"
            )
    return model


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return value
    if hasattr(value, "value"):
        return value.value
    return value
