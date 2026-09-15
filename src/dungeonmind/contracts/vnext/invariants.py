"""Canonical semantic-invariant manifest for vNext contract identity.

JSON Schema captures structural wire shape. This manifest captures the
binding validator semantics that Pydantic JSON Schema does not encode.
Together they form the cross-repository contract identity hashed into the
checked-in bundle aggregate.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter, ValidationError

from ..semantic_profile import SemanticProfileRef
from .common import (
    LabelsAnyVisibility,
    NonBlankId,
    ScopeSelector,
    Sha256Hex,
    UtcIntervalTemporalScope,
)
from .domain import LiteralValue, SemanticProfileDescriptorV2
from .knowledge import (
    IdentityDecisionKind,
    IdentityDecisionV3,
    PublishKnowledgeRevisionCommand,
)

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
            "reject_examples": [{"kind": "labels_any", "labels": ["org:a", "org:a"]}],
            "accept_examples": [{"kind": "labels_any", "labels": ["org:a", "org:b"]}],
        },
    },
    {
        "invariant_id": "vnext.model.SemanticProfileDescriptorV2.term_namespaces",
        "applies_to": ["SemanticProfileDescriptorV2.term_namespaces"],
        "kind": "collection_item_semantic",
        "definition": {
            "rules": [
                "each_item_must_be_non_empty",
                "each_item_must_not_contain_colon",
                "each_item_must_not_contain_uppercase",
                "each_item_must_not_contain_whitespace",
            ],
            "reject_examples": [
                {
                    "profile_id": "organization.memory",
                    "profile_revision": "1",
                    "term_namespaces": [""],
                },
                {
                    "profile_id": "organization.memory",
                    "profile_revision": "1",
                    "term_namespaces": ["org:ns"],
                },
                {
                    "profile_id": "organization.memory",
                    "profile_revision": "1",
                    "term_namespaces": ["Organization"],
                },
                {
                    "profile_id": "organization.memory",
                    "profile_revision": "1",
                    "term_namespaces": ["org ns"],
                },
            ],
            "accept_examples": [
                {
                    "profile_id": "organization.memory",
                    "profile_revision": "1",
                    "term_namespaces": ["organization", "hr"],
                }
            ],
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
            ],
            "reject_examples": [
                {
                    "decision_id": "iddec:alias",
                    "space_id": "space:x",
                    "decision_kind": "alias_add",
                    "subject_entity_ids": ["a"],
                    "target_entity_ids": [],
                    "alias": None,
                    "created_at": "2026-09-14T00:00:00Z",
                },
                {
                    "decision_id": "iddec:alias-rm",
                    "space_id": "space:x",
                    "decision_kind": "alias_remove",
                    "subject_entity_ids": ["a"],
                    "target_entity_ids": [],
                    "alias": None,
                    "created_at": "2026-09-14T00:00:00Z",
                },
                {
                    "decision_id": "iddec:merge",
                    "space_id": "space:x",
                    "decision_kind": "merge",
                    "subject_entity_ids": ["a"],
                    "target_entity_ids": ["merged"],
                    "created_at": "2026-09-14T00:00:00Z",
                },
                {
                    "decision_id": "iddec:split",
                    "space_id": "space:x",
                    "decision_kind": "split",
                    "subject_entity_ids": ["a"],
                    "target_entity_ids": ["b"],
                    "created_at": "2026-09-14T00:00:00Z",
                },
                {
                    "decision_id": "iddec:unmerge",
                    "space_id": "space:x",
                    "decision_kind": "unmerge",
                    "subject_entity_ids": ["a"],
                    "target_entity_ids": [],
                    "created_at": "2026-09-14T00:00:00Z",
                },
            ],
            "accept_examples": [
                {
                    "decision_id": "iddec:alias-ok",
                    "space_id": "space:x",
                    "decision_kind": "alias_add",
                    "subject_entity_ids": ["a"],
                    "target_entity_ids": [],
                    "alias": "aka",
                    "created_at": "2026-09-14T00:00:00Z",
                },
                {
                    "decision_id": "iddec:merge-ok",
                    "space_id": "space:x",
                    "decision_kind": "merge",
                    "subject_entity_ids": ["a", "b"],
                    "target_entity_ids": ["merged"],
                    "created_at": "2026-09-14T00:00:00Z",
                },
                {
                    "decision_id": "iddec:split-ok",
                    "space_id": "space:x",
                    "decision_kind": "split",
                    "subject_entity_ids": ["a"],
                    "target_entity_ids": ["b", "c"],
                    "created_at": "2026-09-14T00:00:00Z",
                },
                {
                    "decision_id": "iddec:unmerge-ok",
                    "space_id": "space:x",
                    "decision_kind": "unmerge",
                    "subject_entity_ids": ["merged"],
                    "target_entity_ids": ["a"],
                    "created_at": "2026-09-14T00:00:00Z",
                },
            ],
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
            "accept_example": {
                "profile_id": "organization.memory",
                "profile_revision": "1",
                "descriptor_sha256": "a" * 64,
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
            ],
            "reject_examples": [
                {
                    "parent_revision_id": "rev:a",
                    "expected_parent_revision_id": "rev:b",
                    "operation_ids": ["op:1"],
                    "graph_payload": {},
                },
                {
                    "parent_revision_id": None,
                    "expected_parent_revision_id": None,
                    "operation_ids": [],
                    "graph_payload": {},
                },
            ],
            # Non-JSON values cannot live in the hashed manifest payload;
            # named probes keep that rule executable and binding.
            "runtime_reject_probes": ["graph_payload_non_finite_float"],
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
            "runtime_reject_probes": [
                "non_finite_float_nan",
                "non_finite_float_inf",
                "non_str_dict_key",
                "non_json_object",
            ],
            "accept_examples": [None, "ok", True, 1, 1.5, [1, "a"], {"k": [None]}],
        },
    },
)

_JSON_REJECT_PROBES: dict[str, Any] = {
    "non_finite_float_nan": math.nan,
    "non_finite_float_inf": math.inf,
    "non_str_dict_key": {1: "x"},
    "non_json_object": object(),
}


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


def _require_model_rejects(model: type[Any], examples: list[Any], *, label: str) -> None:
    for example in examples:
        try:
            model.model_validate(example)
        except ValidationError:
            continue
        raise AssertionError(f"{label} unexpectedly accepted {example!r}")


def _require_model_accepts(model: type[Any], examples: list[Any], *, label: str) -> None:
    for example in examples:
        model.model_validate(example)


def _check_nonblank(row: dict[str, Any]) -> None:
    definition = row["definition"]
    adapter = TypeAdapter(NonBlankId)
    _require_rejects(adapter, definition["reject_examples"], label="NonBlankId")
    _require_accepts(adapter, definition["accept_examples"], label="NonBlankId")


def _check_sha256(row: dict[str, Any]) -> None:
    definition = row["definition"]
    adapter = TypeAdapter(Sha256Hex)
    _require_rejects(adapter, definition["reject_examples"], label="Sha256Hex")
    _require_accepts(adapter, definition["accept_examples"], label="Sha256Hex")


def _check_unique_members(row: dict[str, Any]) -> None:
    definition = row["definition"]
    _require_model_rejects(
        LabelsAnyVisibility,
        definition["reject_examples"],
        label="unique_members",
    )
    _require_model_accepts(
        LabelsAnyVisibility,
        definition["accept_examples"],
        label="unique_members",
    )


def _check_term_namespaces(row: dict[str, Any]) -> None:
    definition = row["definition"]
    _require_model_rejects(
        SemanticProfileDescriptorV2,
        definition["reject_examples"],
        label="term_namespaces",
    )
    _require_model_accepts(
        SemanticProfileDescriptorV2,
        definition["accept_examples"],
        label="term_namespaces",
    )


def _check_scope_selector(row: dict[str, Any]) -> None:
    definition = row["definition"]
    _require_model_rejects(
        ScopeSelector,
        definition["reject_examples"],
        label="ScopeSelector",
    )


def _check_utc_bounds(row: dict[str, Any]) -> None:
    definition = row["definition"]
    _require_model_rejects(
        UtcIntervalTemporalScope,
        definition["reject_examples"],
        label="UtcIntervalTemporalScope",
    )
    _require_model_accepts(
        UtcIntervalTemporalScope,
        definition["accept_examples"],
        label="UtcIntervalTemporalScope",
    )


def _check_identity_cardinality(row: dict[str, Any]) -> None:
    definition = row["definition"]
    _require_model_rejects(
        IdentityDecisionV3,
        definition["reject_examples"],
        label="IdentityDecisionV3",
    )
    _require_model_accepts(
        IdentityDecisionV3,
        definition["accept_examples"],
        label="IdentityDecisionV3",
    )
    # Keep rule table executable: each declared kind is exercised above.
    kinds = {rule["decision_kind"] for rule in definition["rules"]}
    expected = {
        IdentityDecisionKind.ALIAS_ADD.value,
        IdentityDecisionKind.ALIAS_REMOVE.value,
        IdentityDecisionKind.MERGE.value,
        IdentityDecisionKind.SPLIT.value,
        IdentityDecisionKind.UNMERGE.value,
    }
    if kinds != expected:
        raise AssertionError(f"IdentityDecisionV3 rule kinds drifted: {sorted(kinds)}")


def _check_semantic_profile_ref(row: dict[str, Any]) -> None:
    definition = row["definition"]
    base = dict(definition["accept_example"])
    SemanticProfileRef.model_validate(base)
    for field_name, examples in definition["reject_examples"].items():
        for example in examples:
            payload = dict(base)
            payload[field_name] = example
            try:
                SemanticProfileRef.model_validate(payload)
            except ValidationError:
                continue
            raise AssertionError(
                f"SemanticProfileRef unexpectedly accepted {field_name}={example!r}"
            )


def _publish_base(**overrides: Any) -> dict[str, Any]:
    payload = {
        "space_id": "space:x",
        "parent_revision_id": None,
        "expected_parent_revision_id": None,
        "operation_ids": ["op:1"],
        "graph_schema": "dm_graph_v1",
        "graph_payload": {},
        "domain_contract_ref": {
            "domain_id": "organization.memory",
            "domain_revision": "1",
            "descriptor_sha256": "b" * 64,
        },
        "semantic_profile_ref": {
            "profile_id": "organization.memory",
            "profile_revision": "1",
            "descriptor_sha256": "a" * 64,
        },
        "created_at": datetime(2026, 9, 14, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
    }
    payload.update(overrides)
    return payload


def _check_publish_parent_cas(row: dict[str, Any]) -> None:
    definition = row["definition"]
    PublishKnowledgeRevisionCommand.model_validate(_publish_base())
    for example in definition["reject_examples"]:
        payload = _publish_base(**example)
        try:
            PublishKnowledgeRevisionCommand.model_validate(payload)
        except ValidationError:
            continue
        raise AssertionError(
            f"PublishKnowledgeRevisionCommand unexpectedly accepted {example!r}"
        )
    for probe in definition["runtime_reject_probes"]:
        if probe != "graph_payload_non_finite_float":
            raise AssertionError(f"unknown publish probe {probe!r}")
        payload = _publish_base(graph_payload={"bad": math.nan})
        try:
            PublishKnowledgeRevisionCommand.model_validate(payload)
        except ValidationError:
            continue
        raise AssertionError("PublishKnowledgeRevisionCommand unexpectedly accepted NaN payload")


def _check_json_value(row: dict[str, Any]) -> None:
    definition = row["definition"]
    for probe in definition["runtime_reject_probes"]:
        example = _JSON_REJECT_PROBES[probe]
        try:
            LiteralValue.model_validate({"value": example})
        except (ValidationError, TypeError, ValueError):
            continue
        raise AssertionError(f"JsonValue unexpectedly accepted probe {probe!r}")
    for example in definition["accept_examples"]:
        LiteralValue.model_validate({"value": example})


RUNTIME_PARITY_CHECKERS: dict[str, Callable[[dict[str, Any]], None]] = {
    "vnext.value.NonBlankId.reject_whitespace_only": _check_nonblank,
    "vnext.value.Sha256Hex.lowercase_hex_64": _check_sha256,
    "vnext.list.unique_members": _check_unique_members,
    "vnext.model.SemanticProfileDescriptorV2.term_namespaces": _check_term_namespaces,
    "vnext.model.ScopeSelector.no_duplicate_or_overlap": _check_scope_selector,
    "vnext.model.UtcIntervalTemporalScope.bounds": _check_utc_bounds,
    "vnext.model.IdentityDecisionV3.cardinality": _check_identity_cardinality,
    "vnext.reused.SemanticProfileRef.validators": _check_semantic_profile_ref,
    "vnext.model.PublishKnowledgeRevisionCommand.parent_cas": _check_publish_parent_cas,
    "vnext.value.JsonValue.canonical_json_compatible": _check_json_value,
}


def binding_invariant_ids(
    *,
    invariants: tuple[dict[str, Any], ...] | None = None,
) -> set[str]:
    return {item["invariant_id"] for item in (invariants or SEMANTIC_INVARIANTS)}


def assert_checker_ids_match_manifest(
    *,
    invariants: tuple[dict[str, Any], ...] | None = None,
) -> None:
    manifest_ids = binding_invariant_ids(invariants=invariants)
    checker_ids = set(RUNTIME_PARITY_CHECKERS)
    if checker_ids != manifest_ids:
        missing_checkers = sorted(manifest_ids - checker_ids)
        orphan_checkers = sorted(checker_ids - manifest_ids)
        raise AssertionError(
            "runtime parity checkers must equal binding manifest invariant IDs; "
            f"missing_checkers={missing_checkers}; orphan_checkers={orphan_checkers}"
        )


def assert_runtime_matches_manifest(
    *,
    invariants: tuple[dict[str, Any], ...] | None = None,
) -> None:
    """Fail closed if runtime validators disagree with any binding invariant."""
    assert_checker_ids_match_manifest(invariants=invariants)
    rows = {item["invariant_id"]: item for item in (invariants or SEMANTIC_INVARIANTS)}
    for invariant_id in sorted(RUNTIME_PARITY_CHECKERS):
        RUNTIME_PARITY_CHECKERS[invariant_id](rows[invariant_id])
