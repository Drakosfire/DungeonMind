"""Canonical semantic-invariant manifest for vNext contract identity.

JSON Schema captures structural wire shape. This manifest captures the
binding validator semantics that Pydantic JSON Schema does not encode.
Together they form the cross-repository contract identity hashed into the
checked-in bundle aggregate.
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from .common import NonBlankId, ScopeSelector, Sha256Hex, UtcIntervalTemporalScope
from .knowledge import IdentityDecisionKind, IdentityDecisionV3

MANIFEST_SCHEMA = "dm_vnext_semantic_invariant_manifest_v1"

# Explicit, versioned invariant definitions. Changing a binding validator's
# meaning requires updating the corresponding definition here; the bundle
# aggregate includes this manifest and therefore changes.
SEMANTIC_INVARIANTS: tuple[dict[str, Any], ...] = (
    {
        "invariant_id": "vnext.value.NonBlankId.reject_whitespace_only",
        "applies_to": ["NonBlankId"],
        "kind": "string_semantic",
        "definition": {
            "rule": "reject_if_not_str_or_empty_after_str.strip",
            "strip_mode": "str.strip",
            "reject_if_empty_after_strip": True,
            "reject_examples": ["", " ", "   ", "\t", "\n"],
            "accept_examples": ["a", " a ", "priya", "space:x"],
        },
    },
    {
        "invariant_id": "vnext.value.Sha256Hex.lowercase_hex_64",
        "applies_to": ["Sha256Hex"],
        "kind": "string_semantic",
        "definition": {
            "rule": "reject_unless_fullmatch_^[0-9a-f]{64}$",
            "pattern": "^[0-9a-f]{64}$",
            "min_length": 64,
            "max_length": 64,
            "reject_examples": ["g" * 64, " " * 64, "A" * 64, "a" * 63],
            "accept_examples": ["a" * 64, "0123456789abcdef" * 4],
        },
    },
    {
        "invariant_id": "vnext.list.unique_members",
        "applies_to": [
            "LabelsAnyVisibility.labels",
            "LabelsAllVisibility.labels",
            "AssertionMetadata.evidence_ref_ids",
            "DomainContractDescriptor.scope_axes",
            "DomainContractDescriptor.visibility_labels",
            "DomainContractDescriptor.claim_modes",
            "DomainContractDescriptor.temporal_extension_schemas",
            "DomainContractDescriptor.domain_metadata_schemas",
            "DomainContractDescriptor.source_annotation_schemas",
            "SemanticProfileDescriptorV2.term_namespaces",
            "SemanticProfileDescriptorV2.classification_terms",
            "SemanticProfilePredicate.allowed_value_kinds",
            "IdentityAlias.evidence_ref_ids",
            "KnowledgeRevision.operation_ids",
            "PublishKnowledgeRevisionCommand.operation_ids",
            "KnowledgeContribution.source_refs",
            "ContributionDisposition.identity_decision_ids",
            "SourceArtifactV3.foreign_refs",
            "ProjectionRequest.audience_labels",
            "ProjectionRequest.domain_context",
            "ProjectionRequest.standing_selector",
            "ProjectionSnapshot.audience_labels",
            "ProjectionSnapshot.standing_selector",
        ],
        "kind": "collection_semantic",
        "definition": {
            "rule": "reject_if_len_ne_len_set",
            "comparison": "python_set_equality_of_members",
        },
    },
    {
        "invariant_id": "vnext.model.ScopeSelector.no_duplicate_or_overlap",
        "applies_to": ["ScopeSelector"],
        "kind": "model_semantic",
        "definition": {
            "rules": [
                "bindings_axis_value_pairs_must_be_unique",
                "wildcard_axes_must_be_unique",
                "an_axis_cannot_be_both_bound_and_wildcarded",
            ],
            "reject_examples": [
                {
                    "bindings": [
                        {"axis": "organization:team", "value": "research"},
                        {"axis": "organization:team", "value": "research"},
                    ],
                    "wildcard_axes": [],
                },
                {
                    "bindings": [{"axis": "organization:team", "value": "research"}],
                    "wildcard_axes": ["organization:team"],
                },
            ],
        },
    },
    {
        "invariant_id": "vnext.model.UtcIntervalTemporalScope.bounds",
        "applies_to": ["UtcIntervalTemporalScope"],
        "kind": "model_semantic",
        "definition": {
            "rules": [
                "require_at_least_one_of_valid_from_or_valid_until",
                "reject_if_valid_until_precedes_valid_from",
            ],
            "reject_examples": [
                {"kind": "utc_interval"},
                {
                    "kind": "utc_interval",
                    "valid_from": "2026-09-08T00:00:00Z",
                    "valid_until": "2026-09-07T00:00:00Z",
                },
            ],
            "accept_examples": [
                {
                    "kind": "utc_interval",
                    "valid_from": "2026-04-01T00:00:00Z",
                    "valid_until": None,
                },
                {
                    "kind": "utc_interval",
                    "valid_from": "2026-04-01T00:00:00Z",
                    "valid_until": "2026-09-07T00:00:00Z",
                },
            ],
        },
    },
    {
        "invariant_id": "vnext.model.IdentityDecisionV3.cardinality",
        "applies_to": ["IdentityDecisionV3"],
        "kind": "model_semantic",
        "definition": {
            "rules": [
                {
                    "decision_kind": "alias_add",
                    "requires_alias": True,
                },
                {
                    "decision_kind": "alias_remove",
                    "requires_alias": True,
                },
                {
                    "decision_kind": "merge",
                    "min_subjects": 2,
                    "exact_targets": 1,
                },
                {
                    "decision_kind": "split",
                    "exact_subjects": 1,
                    "min_targets": 2,
                },
                {
                    "decision_kind": "unmerge",
                    "min_targets": 1,
                },
            ]
        },
    },
    {
        "invariant_id": "vnext.reused.SemanticProfileRef.validators",
        "applies_to": [
            "KnowledgeRevision.semantic_profile_ref",
            "PublishKnowledgeRevisionCommand.semantic_profile_ref",
            "ProjectionSnapshot.semantic_profile_ref",
        ],
        "kind": "reused_contract_semantic",
        "definition": {
            "contract": "dm_semantic_profile_ref_v1",
            "rules": [
                "profile_id_rejects_latest_whitespace_path_uri_module",
                "profile_id_must_match_^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
                "profile_revision_rejects_latest_whitespace_path_uri_module",
                "profile_revision_must_match_^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
                "descriptor_sha256_must_be_64_lowercase_hex",
            ],
            "reject_examples": {
                "profile_id": ["latest", "Has Space", "a/b", "https://x", "mod.py"],
                "profile_revision": ["latest", "Has Space"],
                "descriptor_sha256": ["g" * 64, "A" * 64],
            },
        },
    },
    {
        "invariant_id": "vnext.model.PublishKnowledgeRevisionCommand.parent_cas",
        "applies_to": ["PublishKnowledgeRevisionCommand"],
        "kind": "model_semantic",
        "definition": {
            "rules": [
                "parent_revision_id_must_equal_expected_parent_revision_id",
                "operation_ids_min_length_1",
                "graph_payload_must_be_canonical_json_compatible",
            ]
        },
    },
    {
        "invariant_id": "vnext.value.JsonValue.canonical_json_compatible",
        "applies_to": [
            "LiteralValue.value",
            "DomainMetadataEntry.payload",
            "DomainTemporalScope.payload",
            "SemanticProfilePredicate.literal_schema",
            "PublishKnowledgeRevisionCommand.graph_payload",
        ],
        "kind": "value_semantic",
        "definition": {
            "rule": "reject_non_finite_floats_non_str_keys_and_non_json_objects",
            "allowed_leaves": ["null", "str", "bool", "int", "finite_float"],
            "allowed_containers": ["list", "dict_with_str_keys"],
        },
    },
)


def semantic_invariant_manifest(
    *,
    invariants: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    rows = list(invariants if invariants is not None else SEMANTIC_INVARIANTS)
    rows.sort(key=lambda item: item["invariant_id"])
    return {
        "manifest_schema": MANIFEST_SCHEMA,
        "invariant_count": len(rows),
        "invariants": rows,
    }


def _require_rejects(adapter: TypeAdapter[Any], examples: list[Any], *, label: str) -> None:
    for example in examples:
        try:
            adapter.validate_python(example)
        except ValidationError:
            continue
        raise AssertionError(f"{label} unexpectedly accepted {example!r}")


def _require_accepts(adapter: TypeAdapter[Any], examples: list[Any], *, label: str) -> None:
    for example in examples:
        adapter.validate_python(example)


def assert_runtime_matches_manifest(
    *,
    invariants: tuple[dict[str, Any], ...] | None = None,
) -> None:
    """Fail closed if runtime validators disagree with manifest examples."""
    rows = {item["invariant_id"]: item for item in (invariants or SEMANTIC_INVARIANTS)}

    nonblank = rows["vnext.value.NonBlankId.reject_whitespace_only"]["definition"]
    adapter = TypeAdapter(NonBlankId)
    _require_rejects(adapter, nonblank["reject_examples"], label="NonBlankId")
    _require_accepts(adapter, nonblank["accept_examples"], label="NonBlankId")

    sha = rows["vnext.value.Sha256Hex.lowercase_hex_64"]["definition"]
    sha_adapter = TypeAdapter(Sha256Hex)
    _require_rejects(sha_adapter, sha["reject_examples"], label="Sha256Hex")
    _require_accepts(sha_adapter, sha["accept_examples"], label="Sha256Hex")

    scope = rows["vnext.model.ScopeSelector.no_duplicate_or_overlap"]["definition"]
    for example in scope["reject_examples"]:
        try:
            ScopeSelector.model_validate(example)
        except ValidationError:
            continue
        raise AssertionError(f"ScopeSelector unexpectedly accepted {example!r}")

    utc = rows["vnext.model.UtcIntervalTemporalScope.bounds"]["definition"]
    for example in utc["reject_examples"]:
        try:
            UtcIntervalTemporalScope.model_validate(example)
        except ValidationError:
            continue
        raise AssertionError(f"UtcIntervalTemporalScope unexpectedly accepted {example!r}")
    for example in utc["accept_examples"]:
        UtcIntervalTemporalScope.model_validate(example)

    # Identity cardinality smoke: merge with one subject must fail.
    try:
        IdentityDecisionV3.model_validate(
            {
                "decision_id": "iddec:x",
                "space_id": "space:x",
                "decision_kind": IdentityDecisionKind.MERGE,
                "subject_entity_ids": ["a"],
                "target_entity_ids": ["merged"],
                "created_at": "2026-09-14T00:00:00Z",
            }
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("IdentityDecisionV3 merge cardinality unexpectedly accepted")
