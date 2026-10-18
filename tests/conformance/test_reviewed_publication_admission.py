"""Complete FINAL accepted set and immutable admission correspondence."""

import json

import pytest

from dungeonmind.application.publication_admission import (
    PublicationAdmissionRegistry,
    context_for,
    verify_receipt,
)
from dungeonmind.contracts.publication_admission import (
    CONTEXT_BYTES,
    bounded_canonical,
    bounded_sha256,
)
from dungeonmind.domain.canonical import canonical_sha256
from dungeonmind.domain.errors import PersistenceIntegrityError
from tests.unit.test_contribution_review_v4 import candidate
from tests.unit.test_publication_admission import (
    SyntheticValidator,
    admission_policy,
    counts,
    setup_memory,
)

pytestmark = pytest.mark.conformance


@pytest.mark.parametrize(
    "defect",
    ["role_removed", "swapped_line", "malformed_quantity", "wrong_catalog", "output_mismatch"],
)
def test_synthetic_domain_validates_whole_final_set_and_materialized_output(defect):
    value = candidate()
    if defect == "swapped_line":
        value.assertions[0].evidence_refs[0].source_span_ref_id = "paragraph:999"
        value.assertions[0].evidence_refs[0].evidence_ref_id += ":wrong-line"
    elif defect == "malformed_quantity":
        literal = json.loads(value.assertions[0].value)
        literal["value"]["count"] = "two"
        value.assertions[0].value = json.dumps(literal)
    lane = setup_memory(
        validator=SyntheticValidator(),
        new_candidate=value,
        reject_property=defect == "role_removed",
    )
    ctx, parent, child = context_for(
        lane.state, lane.parent, lane.command, lane.policy, lane.snapshot
    )
    if defect == "wrong_catalog":
        policy = admission_policy(
            lane.policy.profile_ref,
            catalogs=[dict(catalog_id="wrong", catalog_version="v1", catalog_sha256="a" * 64)],
        )
        raw = ctx.model_dump(mode="json")
        raw.update(
            admission_policy_ref=policy.reference.model_dump(mode="json"),
            catalog_refs=[r.model_dump(mode="json") for r in policy.catalog_refs],
        )
        from dungeonmind.contracts.publication_admission import PublicationAdmissionContextV1

        ctx = PublicationAdmissionContextV1.model_validate(raw)
    else:
        policy = lane.policy
    if defect == "output_mismatch":
        changed = json.loads(child)
        for obj in changed["objects"]:
            obj["properties"] = []
        child = bounded_canonical(changed, max_bytes=64 * 1024 * 1024)
        ctx = ctx.model_copy(update={"child_graph_payload_sha256": canonical_sha256(changed)})
    with pytest.raises(PersistenceIntegrityError):
        lane.publications._admission_registry.validate(
            policy,
            bounded_canonical(ctx.model_dump(mode="json"), max_bytes=CONTEXT_BYTES),
            parent,
            child,
        )


@pytest.mark.parametrize(
    "corruption", ["context", "accepted", "snapshot", "policy", "child", "parent"]
)
def test_restart_receipt_verification_rejects_corrupt_retained_or_actual_authority(corruption):
    lane = setup_memory(validator=SyntheticValidator())
    receipt = lane.publications.publish(lane.command)
    child = lane.graph.get_revision(receipt.world_id, receipt.published_revision_id)
    if corruption == "policy":
        lane.authority._policies[
            (lane.policy.profile_ref.profile_id, lane.policy.profile_ref.profile_revision)
        ]["validator_ref"]["validator_version"] = "wrong"
    elif corruption in ("parent", "child"):
        target = lane.parent if corruption == "parent" else child
        target.graph_payload["objects"][0]["label"] = "altered"
    else:
        ctx = receipt.admission_context
        if corruption == "context":
            object.__setattr__(ctx, "review_id", "another-review")
        elif corruption == "accepted":
            ctx.accepted_assertions[0]["label"] = "changed"
        else:
            object.__setattr__(ctx.source_snapshot.revisions[0], "content_sha256", "0" * 64)
        # Even coherent context rehashing cannot sever its review/graph binding.
        object.__setattr__(
            receipt,
            "admission_context_sha256",
            bounded_sha256(ctx.model_dump(mode="json"), max_bytes=CONTEXT_BYTES),
        )
    with pytest.raises((PersistenceIntegrityError, ValueError)):
        from dungeonmind.contracts.review_publication import (
            decode_finalized_review_publication,
            publication_record_payload,
        )

        receipt = decode_finalized_review_publication(publication_record_payload(receipt))
        verify_receipt(
            receipt, lane.state, lane.parent, child, lane.authority.get(lane.policy.profile_ref)
        )


def test_registry_rejects_duplicate_composition_and_strict_mutated_result():
    validator = SyntheticValidator()
    with pytest.raises(ValueError):
        PublicationAdmissionRegistry((("v", "1", validator), ("v", "1", validator)))

    class CorruptResult:
        def validate(self, *_):
            from dungeonmind.contracts.publication_admission import PublicationAdmissionResultV1

            return PublicationAdmissionResultV1.model_construct(decision=True, reason="accepted")

    lane = setup_memory(validator=CorruptResult())
    before = counts(lane)
    with pytest.raises(PersistenceIntegrityError) as exc:
        lane.publications.publish(lane.command)
    assert exc.value.details["reason"] == "validator_failed" and counts(lane) == before
