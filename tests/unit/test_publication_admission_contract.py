"""Admission canonical byte/collection boundaries and raw reconstruction safety."""

import pytest
from pydantic import ValidationError

from dungeonmind.contracts.publication_admission import (
    ACCEPTED_BYTES,
    CONTEXT_BYTES,
    GRAPH_BYTES,
    POLICY_BYTES,
    SOURCE_BYTES,
    AdmissionSourceSnapshotV1,
    PublicationAdmissionPolicyV1,
    bounded_canonical,
    opaque,
    strict_json_loads,
)
from dungeonmind.contracts.review_publication import (
    FinalizedReviewPublicationCommandV2,
    GuardedFinalizedReviewPublicationCommandV2,
    decode_finalized_review_publication_command,
    publication_record_payload,
)
from dungeonmind.domain.canonical import canonical_json
from tests.unit.test_contribution_review_v2 import PROFILE
from tests.unit.test_publication_admission import SyntheticValidator, admission_policy, setup_memory


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        123,
        -0.0,
        1e-20,
        [True, None, 1.0],
        {"é": 'quote"\\\t\n🙂', "a": [0.1, -123, {"日本語": "value"}]},
        "é" * 2049,
    ],
)
def test_bounded_encoder_matches_frozen_core_canonical(value):
    assert bounded_canonical(value, max_bytes=100_000) == canonical_json(value).encode()


@pytest.mark.parametrize(
    "limit", [POLICY_BYTES, SOURCE_BYTES, ACCEPTED_BYTES, CONTEXT_BYTES, GRAPH_BYTES]
)
def test_exact_and_one_over_every_canonical_byte_budget(limit):
    exact = "x" * (limit - 2)
    assert len(bounded_canonical(exact, max_bytes=limit)) == limit
    with pytest.raises(ValueError, match="limit_exceeded"):
        bounded_canonical(exact + "x", max_bytes=limit)


def test_actual_depth_and_million_node_boundaries():
    value = None
    for _ in range(64):
        value = [value]
    bounded_canonical(value, max_bytes=1024)
    with pytest.raises(ValueError, match="limit_exceeded"):
        bounded_canonical([value], max_bytes=1024)
    nodes = [None] * 999_999
    bounded_canonical(nodes, max_bytes=GRAPH_BYTES)
    with pytest.raises(ValueError, match="limit_exceeded"):
        bounded_canonical([*nodes, None], max_bytes=GRAPH_BYTES)
    assert bounded_canonical({"x": None}, max_bytes=20, max_nodes=3) == b'{"x":null}'
    with pytest.raises(ValueError):
        bounded_canonical({"x": None}, max_bytes=20, max_nodes=2)


@pytest.mark.parametrize(
    "value",
    [
        {1: "x"},
        (1, 2),
        {"a": float("nan")},
        {"a": float("inf")},
        {"a": b"bytes"},
        {"a": {1}},
        object(),
    ],
)
def test_raw_non_json_types_never_coerce(value):
    with pytest.raises(ValueError):
        bounded_canonical(value, max_bytes=1000)


@pytest.mark.parametrize(
    "raw", [b'{"a":1,"a":2}', b'{"nested":{"x":1,"x":2}}', b'{"x":NaN}', b'{"x":Infinity}']
)
def test_raw_bytes_duplicate_keys_and_nonfinite_rejected(raw):
    with pytest.raises(ValueError):
        strict_json_loads(raw)


def test_opaque_utf8_exact_and_one_over_no_normalization():
    assert opaque("é" * 256) == "é" * 256
    for value in ("é" * 256 + "x", "x" * 513, " bad", "bad ", "", " "):
        with pytest.raises(ValueError):
            opaque(value)


def test_catalog_exact_64_one_over_and_unsorted_duplicate_conflicting_policy():
    catalogs = [
        dict(catalog_id=f"c:{i:02}", catalog_version="1", catalog_sha256="a" * 64)
        for i in range(64)
    ]
    assert len(admission_policy(PROFILE, catalogs=catalogs).catalog_refs) == 64
    for rows in (
        [*catalogs, dict(catalogs[-1], catalog_id="last")],
        list(reversed(catalogs)),
        [catalogs[0], catalogs[0]],
    ):
        with pytest.raises(ValidationError):
            admission_policy(PROFILE, catalogs=rows)
    raw = admission_policy(PROFILE).model_dump(mode="json")
    raw["validator_ref"]["validator_version"] = "other"
    with pytest.raises(ValidationError):
        PublicationAdmissionPolicyV1.model_validate(raw)


def test_source_collections_exact_4096_one_over_and_closure():
    ids = [f"id:{i:04}" for i in range(4096)]
    raw = dict(
        requested_artifact_ids=ids,
        requested_revision_ids=ids,
        missing_artifact_ids=ids,
        missing_revision_ids=ids,
        artifacts=[],
        revisions=[],
    )
    AdmissionSourceSnapshotV1(**raw)
    for field in (
        "requested_artifact_ids",
        "requested_revision_ids",
        "missing_artifact_ids",
        "missing_revision_ids",
    ):
        changed = dict(raw, **{field: [*ids, "z"]})
        with pytest.raises(ValidationError):
            AdmissionSourceSnapshotV1(**changed)
    with pytest.raises(ValidationError):
        AdmissionSourceSnapshotV1(**dict(raw, missing_artifact_ids=[]))


def test_actual_nested_model_mutation_revalidated_before_serialization():
    policy = admission_policy(PROFILE)
    object.__setattr__(policy, "catalog_refs", ())
    with pytest.raises((ValueError, ValidationError)):
        PublicationAdmissionPolicyV1.model_validate(policy)
    policy = admission_policy(PROFILE)
    policy.profile_ref.profile_id = "bad "
    with pytest.raises((ValueError, ValidationError)):
        PublicationAdmissionPolicyV1.model_validate(policy)
    lane = setup_memory(validator=SyntheticValidator())
    receipt = lane.publications.publish(lane.command)
    object.__setattr__(
        receipt.admission_context,
        "accepted_assertions",
        tuple(receipt.admission_context.accepted_assertions),
    )
    with pytest.raises((ValueError, ValidationError)):
        publication_record_payload(receipt)


def test_v2_decode_retains_guarded_variant_and_unknown_family_fails():
    lane = setup_memory()
    raw = lane.command.model_dump(mode="json")
    assert isinstance(
        decode_finalized_review_publication_command(raw), FinalizedReviewPublicationCommandV2
    )
    # Use the real guard contract shape from existing unit fixture builders.
    from dungeonmind.contracts.contribution_review_v2 import (
        ReviewedIdentityPublicationPreconditionsV1,
    )

    guard = ReviewedIdentityPublicationPreconditionsV1(
        world_id=lane.command.world_id,
        expected_parent_revision_id=lane.command.expected_parent_revision_id,
        campaign_id="longmont-c2",
        decision_id="decision:test",
        decision_sha256="a" * 64,
        target_object_id="npc:test",
        target_object_sha256="b" * 64,
        existence_evidence_sha256="c" * 64,
        sources=(
            {
                "source_artifact_id": "a",
                "source_revision_id": "r",
                "source_artifact_sha256": "d" * 64,
                "source_revision_sha256": "e" * 64,
            },
        ),
    )
    raw["reviewed_identity_preconditions"] = guard.model_dump(mode="json")
    assert isinstance(
        decode_finalized_review_publication_command(raw), GuardedFinalizedReviewPublicationCommandV2
    )
    raw["schema_version"] = "unknown"
    with pytest.raises(ValueError):
        decode_finalized_review_publication_command(raw)


def test_actual_new_family_json_decoders_reject_duplicate_keys():

    policy = admission_policy(PROFILE)
    raw = policy.model_dump_json()
    duplicate = raw[:-1] + ',"policy_id":"other"}'
    with pytest.raises(ValueError, match="duplicate"):
        PublicationAdmissionPolicyV1.model_validate_json(duplicate)
    lane = setup_memory()
    raw = lane.command.model_dump_json()
    duplicate = raw[:-1] + ',"graph_payload":{}}'
    with pytest.raises(ValueError, match="duplicate"):
        FinalizedReviewPublicationCommandV2.model_validate_json(duplicate)


def context_payload():
    lane = setup_memory(validator=SyntheticValidator())
    return lane.publications.publish(lane.command).admission_context.model_dump(mode="json")


def test_actual_accepted_section_byte_and_count_limits_construct_and_reload():
    from dungeonmind.contracts.publication_admission import PublicationAdmissionContextV1
    from dungeonmind.domain.canonical import canonical_sha256

    raw = context_payload()
    rows = [{"assertion_id": "a", "value": ""}]
    empty_size = len(bounded_canonical(rows, max_bytes=ACCEPTED_BYTES))
    rows[0]["value"] = "x" * (ACCEPTED_BYTES - empty_size)
    raw.update(accepted_assertions=rows, accepted_assertions_sha256=canonical_sha256(rows))
    result = PublicationAdmissionContextV1.model_validate(raw)
    PublicationAdmissionContextV1.model_validate_json(result.model_dump_json())
    rows[0]["value"] += "x"
    raw["accepted_assertions_sha256"] = canonical_sha256(rows)
    with pytest.raises(ValueError, match="limit_exceeded"):
        PublicationAdmissionContextV1.model_validate(raw)
    rows = [{"assertion_id": f"a:{i:04}"} for i in range(4096)]
    raw.update(accepted_assertions=rows, accepted_assertions_sha256=canonical_sha256(rows))
    PublicationAdmissionContextV1.model_validate(raw)
    rows.append({"assertion_id": "z"})
    raw["accepted_assertions_sha256"] = canonical_sha256(rows)
    with pytest.raises(ValueError):
        PublicationAdmissionContextV1.model_validate(raw)


def test_loaded_source_collections_exact_4096_and_opaque_snapshot_values():
    from dungeonmind.contracts.publication_admission import AdmissionSourceSnapshotV1

    raw = context_payload()["source_snapshot"]
    artifact_template = raw["artifacts"][0]
    revision_template = raw["revisions"][0]
    artifacts = [dict(artifact_template, source_artifact_id=f"a:{i:04}") for i in range(4096)]
    revisions = [
        dict(revision_template, source_revision_id=f"r:{i:04}", source_artifact_id=f"a:{i:04}")
        for i in range(4096)
    ]
    raw.update(
        artifacts=artifacts,
        revisions=revisions,
        requested_artifact_ids=[a["source_artifact_id"] for a in artifacts],
        requested_revision_ids=[r["source_revision_id"] for r in revisions],
    )
    AdmissionSourceSnapshotV1.model_validate(raw)
    for field, row in (
        ("artifacts", dict(artifact_template, source_artifact_id="z")),
        ("revisions", dict(revision_template, source_revision_id="z")),
    ):
        changed = dict(raw, **{field: [*raw[field], row]})
        with pytest.raises(ValueError):
            AdmissionSourceSnapshotV1.model_validate(changed)
    raw["artifacts"][0]["document_class"] = "é" * 256
    AdmissionSourceSnapshotV1.model_validate(raw)
    raw["artifacts"][0]["document_class"] += "x"
    with pytest.raises(ValueError, match="limit_exceeded"):
        AdmissionSourceSnapshotV1.model_validate(raw)


def test_actual_source_snapshot_exact_8mib_and_one_over():
    from dungeonmind.contracts.publication_admission import AdmissionSourceSnapshotV1

    raw = context_payload()["source_snapshot"]
    template = raw["artifacts"][0]
    fields = [
        key
        for key in template
        if key
        not in (
            "schema_version",
            "source_schema_version",
            "source_artifact_id",
            "world_id",
            "workspace_document_ref",
            "status",
        )
    ]
    artifacts = [
        dict(template, source_artifact_id=f"a:{i:04}", **{key: None for key in fields})
        for i in range(1600)
    ]
    raw.update(
        artifacts=artifacts,
        revisions=[],
        requested_revision_ids=[],
        requested_artifact_ids=[a["source_artifact_id"] for a in artifacts],
    )
    size = len(bounded_canonical(raw, max_bytes=SOURCE_BYTES))
    remaining = SOURCE_BYTES - size
    last = None
    for row in artifacts:
        for field in fields:
            if remaining == 0:
                break
            delta = min(510, remaining)
            row[field] = "x" * (delta + 2)  # null -> quoted string adds exactly delta bytes
            remaining -= delta
            last = (row, field)
        if remaining == 0:
            break
    assert remaining == 0
    assert len(bounded_canonical(raw, max_bytes=SOURCE_BYTES)) == SOURCE_BYTES
    AdmissionSourceSnapshotV1.model_validate(raw)
    row, field = last
    # Choose a null field if the last filled field reached the opaque limit.
    if len(row[field]) == 512:
        null_row = next(a for a in artifacts if any(a[k] is None for k in fields))
        null_field = next(k for k in fields if null_row[k] is None)
        null_row[null_field] = "xxx"  # +1 byte, still a valid opaque string
    else:
        row[field] += "x"
    with pytest.raises(ValueError, match="limit_exceeded"):
        AdmissionSourceSnapshotV1.model_validate(raw)


def test_durable_reload_never_invents_missing_nested_family_tags():
    from dungeonmind.contracts.review_publication import decode_finalized_review_publication

    policy = admission_policy(PROFILE).model_dump(mode="json")
    del policy["profile_ref"]["schema_version"]
    with pytest.raises(ValueError):
        PublicationAdmissionPolicyV1.model_validate(policy)
    lane = setup_memory(validator=SyntheticValidator())
    raw = lane.publications.publish(lane.command).model_dump(mode="json")
    del raw["admission_context"]["source_snapshot"]["revisions"][0]["schema_version"]
    with pytest.raises(ValueError):
        decode_finalized_review_publication(raw)
