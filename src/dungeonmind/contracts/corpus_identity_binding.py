"""Reviewed typed-corpus-key binding to an existing canonical graph node.

This is a preflight contract, not a source of corpus or graph authority. A
confirmation owner must obtain the observed records from authoritative stores
under its own concurrency fence before calling the validator.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from .base import DungeonMindModel

_SHA256 = r"^[0-9a-f]{64}$"


class CorpusIdentityKeyV1(DungeonMindModel):
    model_config = ConfigDict(frozen=True)
    namespace: str = Field(min_length=1)
    key_type: str = Field(min_length=1)
    value: str = Field(min_length=1)

    @field_validator("namespace", "key_type", "value")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("identity key components must be nonblank and unpadded")
        return value


class ReviewedCorpusIdentityBindingV1(DungeonMindModel):
    """Reviewed intent; never infer identity from a label or alias."""

    model_config = ConfigDict(frozen=True)
    schema_version: Literal["dm_reviewed_corpus_identity_binding_v1"] = (
        "dm_reviewed_corpus_identity_binding_v1"
    )
    world_id: str = Field(min_length=1)
    # None is an explicit world-owned source scope, not an omitted field.
    campaign_id: str | None = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_revision_id: str = Field(min_length=1)
    source_body_sha256: str = Field(pattern=_SHA256)
    hub_assertion_id: str = Field(min_length=1)
    hub_assertion_sha256: str = Field(pattern=_SHA256)
    identity_key: CorpusIdentityKeyV1
    asserted_target_id: str = Field(min_length=1)
    asserted_target_kind: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    target_node_kind: str = Field(min_length=1)
    expected_graph_head_revision_id: str = Field(min_length=1)

    @field_validator(
        "world_id", "source_artifact_id", "source_revision_id",
        "hub_assertion_id", "asserted_target_id", "asserted_target_kind",
        "target_node_id", "target_node_kind", "expected_graph_head_revision_id",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("binding identifiers must be nonblank and unpadded")
        return value

    @field_validator("campaign_id")
    @classmethod
    def _campaign_scope(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("campaign scope must be null or nonblank and unpadded")
        return value


class ObservedHubIdentityAssertionV1(DungeonMindModel):
    """Exact assertion resolved from the authoritative pinned corpus revision."""

    model_config = ConfigDict(frozen=True)
    assertion_id: str
    assertion_sha256: str = Field(pattern=_SHA256)
    identity_key: CorpusIdentityKeyV1
    asserted_target_id: str
    asserted_target_kind: str


class CorpusIdentityAuthoritySnapshotV1(DungeonMindModel):
    """Trusted, transaction-fenced observation; not a public request payload."""

    model_config = ConfigDict(frozen=True)
    world_id: str
    campaign_id: str | None
    source_artifact_id: str
    current_source_revision_id: str
    source_body_sha256: str = Field(pattern=_SHA256)
    hub_assertions: tuple[ObservedHubIdentityAssertionV1, ...]
    graph_head_revision_id: str
    target_node_id: str
    target_node_kind: str
    # Must be a complete world-wide accepted-binding lookup, across campaigns.
    # The model cannot prove that a caller actually performed that lookup.
    existing_bindings: tuple[ReviewedCorpusIdentityBindingV1, ...] = ()


def validate_reviewed_corpus_identity_binding(
    binding: ReviewedCorpusIdentityBindingV1,
    observed: CorpusIdentityAuthoritySnapshotV1,
) -> None:
    """Fail closed before mutation; the caller owns authoritative reads/locking."""

    if (binding.world_id, binding.campaign_id) != (observed.world_id, observed.campaign_id):
        raise ValueError("world/campaign scope changed")
    if binding.source_artifact_id != observed.source_artifact_id:
        raise ValueError("source artifact changed")
    if (binding.source_revision_id, binding.source_body_sha256) != (
        observed.current_source_revision_id, observed.source_body_sha256
    ):
        raise ValueError("exact source revision or body changed")
    if binding.expected_graph_head_revision_id != observed.graph_head_revision_id:
        raise ValueError("graph head changed")
    if (binding.target_node_id, binding.target_node_kind) != (
        observed.target_node_id, observed.target_node_kind
    ):
        raise ValueError("target node identity or kind changed")
    if (binding.asserted_target_id, binding.asserted_target_kind) != (
        binding.target_node_id, binding.target_node_kind
    ):
        raise ValueError("hub assertion target differs from canonical node")

    matches = [
        assertion for assertion in observed.hub_assertions
        if assertion.assertion_id == binding.hub_assertion_id
        and assertion.assertion_sha256 == binding.hub_assertion_sha256
        and assertion.identity_key == binding.identity_key
        and assertion.asserted_target_id == binding.asserted_target_id
        and assertion.asserted_target_kind == binding.asserted_target_kind
    ]
    key_claims = [
        assertion for assertion in observed.hub_assertions
        if assertion.identity_key == binding.identity_key
    ]
    if len(matches) != 1 or len(key_claims) != 1:
        raise ValueError("hub identity assertion is missing, ambiguous, or changed")
    for accepted in observed.existing_bindings:
        if accepted.world_id != binding.world_id:
            continue
        if (
            accepted.identity_key == binding.identity_key
            and accepted.target_node_id != binding.target_node_id
        ):
            raise ValueError("typed identity key already binds another node")
        if (
            accepted.target_node_id == binding.target_node_id
            and accepted.identity_key != binding.identity_key
        ):
            raise ValueError("canonical node already binds another typed key")
