"""Closed protected-publication contracts and bounded canonical JSON.

No executable locators, source bodies, callbacks or caller validation claims live
in these records. Limits apply only to the new protected admission family.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Annotated, Any, Literal, Self, cast

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from .base import DungeonMindModel
from .semantic_profile import SemanticProfileRef

CONTEXT_BYTES = 32 * 1024 * 1024
ACCEPTED_BYTES = 16 * 1024 * 1024
SOURCE_BYTES = 8 * 1024 * 1024
POLICY_BYTES = 256 * 1024
GRAPH_BYTES = 64 * 1024 * 1024
MAX_COLLECTION = 4096
MAX_DEPTH = 64
MAX_NODES = 1_000_000


def opaque(value: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError("admission identity must be a strict nonblank string")
    if len(value) > 512 or len(value.encode("utf-8")) > 512:
        raise ValueError("admission_context_limit_exceeded")
    return value


def digest(value: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("admission digest must be lowercase SHA256")
    return value


Opaque = Annotated[str, AfterValidator(opaque)]
Digest = Annotated[str, AfterValidator(digest)]


def bounded_canonical(
    value: Any, *, max_bytes: int, max_depth: int = MAX_DEPTH, max_nodes: int = MAX_NODES
) -> bytes:
    """Core canonical algorithm, strict raw types, bounded retained allocation.

    Encode strings in bounded chunks; JSON escapes are independent per codepoint.
    Do not call coercive model serialization on untrusted raw JSON first.
    """
    output = bytearray()
    nodes = 0

    def emit(piece: str) -> None:
        encoded = piece.encode("utf-8")
        if len(output) + len(encoded) > max_bytes:
            raise ValueError("admission_context_limit_exceeded")
        output.extend(encoded)

    def string(text: str) -> None:
        emit('"')
        for start in range(0, len(text), 2048):
            emit(json.dumps(text[start : start + 2048], ensure_ascii=False)[1:-1])
        emit('"')

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if depth > max_depth or nodes > max_nodes:
            raise ValueError("admission_context_limit_exceeded")
        kind = type(item)
        if kind is dict:
            # Check keys before sorting; never invoke foreign comparison methods.
            if any(type(key) is not str for key in item):
                raise ValueError("admission JSON keys must be strings")
            if len(item) > max_nodes - nodes:
                raise ValueError("admission_context_limit_exceeded")
            emit("{")
            for index, key in enumerate(sorted(item)):
                nodes += 1
                if nodes > max_nodes:
                    raise ValueError("admission_context_limit_exceeded")
                if index:
                    emit(",")
                string(key)
                emit(":")
                visit(item[key], depth + 1)
            emit("}")
        elif kind is list:
            emit("[")
            for index, child in enumerate(item):
                if index:
                    emit(",")
                visit(child, depth + 1)
            emit("]")
        elif kind is str:
            string(item)
        elif item is None or kind in (bool, int, float):
            if kind is float and not math.isfinite(cast(float, item)):
                raise ValueError("admission JSON must be finite")
            # Bound integers before conversion (including Python's digit guard).
            if kind is int and cast(int, item).bit_length() > max_bytes * 4:
                raise ValueError("admission_context_limit_exceeded")
            emit(json.dumps(item, allow_nan=False))
        else:
            raise ValueError("admission JSON contains a non-JSON raw type")

    visit(value, 0)
    return bytes(output)


def bounded_sha256(value: Any, *, max_bytes: int) -> str:
    return hashlib.sha256(bounded_canonical(value, max_bytes=max_bytes)).hexdigest()


def strict_json_loads(value: bytes, *, max_bytes: int = CONTEXT_BYTES) -> Any:
    """Raw bytes boundary: reject duplicate keys before dict construction."""
    if type(value) is not bytes or len(value) > max_bytes:
        raise ValueError("admission_context_limit_exceeded")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate admission JSON key")
            result[key] = item
        return result

    parsed = json.loads(
        value,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    bounded_canonical(parsed, max_bytes=max_bytes)
    return parsed


def strict_contract_payload(value: Any, depth: int = 0, _count: list[int] | None = None) -> Any:
    """Read actual nested model values before any coercive model_dump.

    Frozen models do not recursively freeze their lists or older profile models.
    Treat existing instances exactly like fresh untrusted contract payloads.
    """
    if _count is None:
        _count = [0]
    _count[0] += 1
    if depth > MAX_DEPTH or _count[0] > MAX_NODES:
        raise ValueError("admission_context_limit_exceeded")
    if isinstance(value, BaseModel):
        if value.__pydantic_extra__ or set(value.__dict__) - set(type(value).model_fields):
            raise ValueError("unexpected admission model fields")
        return {
            key: strict_contract_payload(value.__dict__[key], depth + 1, _count)
            for key in type(value).model_fields
        }
    if type(value) is dict:
        _count[0] += len(value)
        if _count[0] > MAX_NODES:
            raise ValueError("admission_context_limit_exceeded")
        if any(type(key) is not str for key in value):
            raise ValueError("admission JSON keys must be strict strings")
        return {
            key: strict_contract_payload(item, depth + 1, _count) for key, item in value.items()
        }
    if type(value) is list:
        if len(value) > MAX_NODES - _count[0]:
            raise ValueError("admission_context_limit_exceeded")
        return [strict_contract_payload(item, depth + 1, _count) for item in value]
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise ValueError("non-JSON raw admission value")


class _Closed(DungeonMindModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
        hide_input_in_errors=True,
    )

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> Self:
        raw = strict_contract_payload(obj)
        result = super().model_validate(raw, **kwargs)
        # Durable reconstruction may not manufacture omitted version tags or
        # defaulted fields. Constructors still support their declared defaults.
        if bounded_canonical(raw, max_bytes=CONTEXT_BYTES) != bounded_canonical(
            strict_contract_payload(result), max_bytes=CONTEXT_BYTES
        ):
            raise ValueError("admission reconstruction changed raw contract fields")
        return result

    @classmethod
    def model_validate_json(cls, json_data: str | bytes | bytearray, **kwargs: Any) -> Self:
        if type(json_data) not in (str, bytes, bytearray):
            raise ValueError("admission JSON input must be text or bytes")
        raw = (
            cast(str, json_data).encode("utf-8")
            if type(json_data) is str
            else bytes(cast(bytes | bytearray, json_data))
        )
        return cls.model_validate(strict_json_loads(raw), **kwargs)

    @model_validator(mode="before")
    @classmethod
    def actual_values(cls, value: Any) -> Any:
        raw = strict_contract_payload(value)
        bounded_canonical(raw, max_bytes=CONTEXT_BYTES)
        return raw


class AdmissionValidatorRefV1(_Closed):
    validator_id: Opaque
    validator_version: Opaque


class AdmissionCatalogRefV1(_Closed):
    catalog_id: Opaque
    catalog_version: Opaque
    catalog_sha256: Digest


class AdmissionPolicyRefV1(_Closed):
    profile_ref: SemanticProfileRef
    policy_id: Opaque
    policy_sha256: Digest

    @field_validator("profile_ref")
    @classmethod
    def bounded_profile(cls, value: SemanticProfileRef) -> SemanticProfileRef:
        opaque(value.profile_id)
        opaque(value.profile_revision)
        return value


class PublicationAdmissionPolicyV1(_Closed):
    schema_version: Literal["dm_publication_admission_policy_v1"] = (
        "dm_publication_admission_policy_v1"
    )
    profile_ref: SemanticProfileRef
    policy_id: Opaque
    validator_ref: AdmissionValidatorRefV1
    catalog_refs: list[AdmissionCatalogRefV1] = Field(max_length=64)
    policy_sha256: Digest

    @model_validator(mode="after")
    def identity(self) -> Self:
        opaque(self.profile_ref.profile_id)
        opaque(self.profile_ref.profile_revision)
        keys = [(v.catalog_id, v.catalog_version, v.catalog_sha256) for v in self.catalog_refs]
        if len(keys) > 64:
            raise ValueError("admission_context_limit_exceeded")
        if keys != sorted(set(keys)):
            raise ValueError("catalog references must be sorted unique")
        payload = self.model_dump(mode="json", exclude={"policy_sha256"})
        if bounded_sha256(payload, max_bytes=POLICY_BYTES) != self.policy_sha256:
            raise ValueError("admission policy digest mismatch")
        return self

    @property
    def reference(self) -> AdmissionPolicyRefV1:
        return AdmissionPolicyRefV1(
            profile_ref=self.profile_ref, policy_id=self.policy_id, policy_sha256=self.policy_sha256
        )


class AdmissionWorkspaceDocumentRefV1(_Closed):
    document_id: Opaque
    revision: int

    @field_validator("revision")
    @classmethod
    def positive_revision(cls, value: int) -> int:
        if value < 1:
            raise ValueError("workspace revision must be positive")
        return value


class AdmissionSourceArtifactSnapshotV1(_Closed):
    schema_version: Literal["dm_admission_source_artifact_snapshot_v1"] = (
        "dm_admission_source_artifact_snapshot_v1"
    )
    source_schema_version: Literal["dm_source_artifact_v1", "dm_source_artifact_v2"]
    source_artifact_id: Opaque
    world_id: Opaque
    campaign_id: Opaque | None
    session_id: Opaque | None
    source_domain: Opaque | None
    source_domain_key: Opaque | None
    current_revision_id: Opaque | None
    authority: Opaque | None
    visibility: Opaque | None
    status: Opaque
    artifact_kind: Opaque | None
    document_class: Opaque | None
    review_state: Opaque | None
    source_visibility_state: Opaque | None
    workspace_document_ref: AdmissionWorkspaceDocumentRefV1 | None

    @model_validator(mode="after")
    def historical_absence(self) -> Self:
        if self.source_schema_version == "dm_source_artifact_v1" and any(
            getattr(self, field) is not None
            for field in (
                "source_domain_key",
                "artifact_kind",
                "document_class",
                "review_state",
                "source_visibility_state",
                "workspace_document_ref",
            )
        ):
            raise ValueError("v1 source cannot carry inferred v2 fields")
        return self


class AdmissionSourceRevisionSnapshotV1(_Closed):
    schema_version: Literal["dm_admission_source_revision_snapshot_v1"] = (
        "dm_admission_source_revision_snapshot_v1"
    )
    source_schema_version: Literal["dm_source_revision_v1"]
    source_revision_id: Opaque
    source_artifact_id: Opaque
    content_sha256: Digest
    body_storage: Literal["postgres", "object_store", "external"]


def _ordered(values: list[str]) -> None:
    if len(values) > MAX_COLLECTION:
        raise ValueError("admission_context_limit_exceeded")
    for value in values:
        opaque(value)
    if values != sorted(set(values)):
        raise ValueError("admission collection must be sorted unique")


class AdmissionSourceSnapshotV1(_Closed):
    schema_version: Literal["dm_admission_source_snapshot_v1"] = "dm_admission_source_snapshot_v1"
    requested_artifact_ids: list[Opaque] = Field(max_length=MAX_COLLECTION)
    requested_revision_ids: list[Opaque] = Field(max_length=MAX_COLLECTION)
    missing_artifact_ids: list[Opaque] = Field(max_length=MAX_COLLECTION)
    missing_revision_ids: list[Opaque] = Field(max_length=MAX_COLLECTION)
    artifacts: list[AdmissionSourceArtifactSnapshotV1] = Field(max_length=MAX_COLLECTION)
    revisions: list[AdmissionSourceRevisionSnapshotV1] = Field(max_length=MAX_COLLECTION)

    @model_validator(mode="after")
    def closure(self) -> Self:
        for kind, rows, key in (
            ("artifact", self.artifacts, "source_artifact_id"),
            ("revision", self.revisions, "source_revision_id"),
        ):
            requested = getattr(self, f"requested_{kind}_ids")
            missing = getattr(self, f"missing_{kind}_ids")
            loaded = [getattr(row, key) for row in rows]
            for values in (requested, missing, loaded):
                _ordered(values)
            if not set(loaded) <= set(requested) or missing != sorted(set(requested) - set(loaded)):
                raise ValueError("admission source snapshot closure mismatch")
        bounded_canonical(self.model_dump(mode="json"), max_bytes=SOURCE_BYTES)
        return self


class PublicationAdmissionContextV1(_Closed):
    schema_version: Literal["dm_publication_admission_context_v1"] = (
        "dm_publication_admission_context_v1"
    )
    review_id: Opaque
    reviewed_contribution_sha256: Digest
    review_intent_sha256: Digest
    accepted_assertions: list[dict[str, Any]] = Field(max_length=MAX_COLLECTION)
    accepted_assertions_sha256: Digest
    parent_revision_id: Opaque
    parent_graph_payload_sha256: Digest
    child_revision_id: Opaque
    child_graph_payload_sha256: Digest
    admission_policy_ref: AdmissionPolicyRefV1
    validator_ref: AdmissionValidatorRefV1
    catalog_refs: list[AdmissionCatalogRefV1] = Field(max_length=64)
    source_snapshot: AdmissionSourceSnapshotV1
    source_snapshot_sha256: Digest

    @model_validator(mode="before")
    @classmethod
    def raw_json(cls, value: Any) -> Any:
        if type(value) is dict:
            # Nested models are accepted for trusted construction; raw assertion
            # JSON is always checked before Pydantic's coercive serialization.
            assertions = value.get("accepted_assertions")
            if assertions is not None:
                bounded_canonical(assertions, max_bytes=ACCEPTED_BYTES)
        return value

    @model_validator(mode="after")
    def bindings(self) -> Self:
        if len(self.accepted_assertions) > MAX_COLLECTION:
            raise ValueError("admission_context_limit_exceeded")
        ids = [opaque(cast(str, row.get("assertion_id"))) for row in self.accepted_assertions]
        _ordered(ids)
        if (
            bounded_sha256(self.accepted_assertions, max_bytes=ACCEPTED_BYTES)
            != self.accepted_assertions_sha256
        ):
            raise ValueError("accepted assertion digest mismatch")
        if (
            bounded_sha256(self.source_snapshot.model_dump(mode="json"), max_bytes=SOURCE_BYTES)
            != self.source_snapshot_sha256
        ):
            raise ValueError("source snapshot digest mismatch")
        keys = [(v.catalog_id, v.catalog_version, v.catalog_sha256) for v in self.catalog_refs]
        if len(keys) > 64 or keys != sorted(set(keys)):
            raise ValueError("catalog references must be sorted unique and bounded")
        bounded_canonical(
            {
                "admission_policy_ref": self.admission_policy_ref.model_dump(mode="json"),
                "validator_ref": self.validator_ref.model_dump(mode="json"),
                "catalog_refs": [r.model_dump(mode="json") for r in self.catalog_refs],
            },
            max_bytes=POLICY_BYTES,
        )
        bounded_canonical(self.model_dump(mode="json"), max_bytes=CONTEXT_BYTES)
        return self


class PublicationAdmissionResultV1(_Closed):
    schema_version: Literal["dm_publication_admission_result_v1"] = (
        "dm_publication_admission_result_v1"
    )
    decision: Literal["accept", "reject"]
    reason: Literal["accepted", "domain_invalid", "catalog_mismatch", "accepted_set_mismatch"]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.decision == "accept") != (self.reason == "accepted"):
            raise ValueError("admission result decision/reason mismatch")
        return self
